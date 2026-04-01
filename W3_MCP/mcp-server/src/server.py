"""FastMCP entry point for the Indian Financial Intelligence MCP Server."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator

import structlog
from fastmcp import FastMCP
from fastmcp.server.middleware import AuthMiddleware as MCPAuthMiddleware
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .config.settings import settings
from .config.constants import ALL_SCOPES, TIER_SCOPES, TIER_FREE, TIER_PREMIUM, TIER_ANALYST
from .tracing import init_tracing
from .auth.provider import KeycloakAuthProvider
from .auth.middleware import TierToolFilter, TOOL_SCOPE_MAP, tool_scope_specs
from .auth.mcp_keycloak import KeycloakMCPVerifier, finint_component_auth
from .auth.rate_limiter import RateLimiter
from .auth.audit import AuditLogger

_auth_provider = KeycloakAuthProvider()
_tier_filter = TierToolFilter()
_rate_limiter: RateLimiter | None = None
_audit_logger = AuditLogger()


async def _get_rate_limiter() -> RateLimiter | None:
    """Lazily create a RateLimiter backed by Redis."""
    global _rate_limiter
    if _rate_limiter is not None:
        return _rate_limiter
    try:
        import redis.asyncio as aioredis
        r = aioredis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=0,
            decode_responses=True,
        )
        await r.ping()
        _rate_limiter = RateLimiter(r)
        return _rate_limiter
    except Exception as exc:
        structlog.get_logger().warning("rate_limiter_init_failed", error=str(exc))
        return None


async def _ensure_audit_logger() -> None:
    """Lazily initialise the audit logger's Postgres pool."""
    if _audit_logger._pool is None:
        try:
            await _audit_logger.init()
        except Exception as exc:
            structlog.get_logger().warning("audit_logger_init_failed", error=str(exc))

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)
log = structlog.get_logger()

mcp = FastMCP(
    "Indian Financial Intelligence",
    instructions=(
        "MCP server providing Indian financial data, cross-source analysis, "
        "portfolio risk monitoring, and earnings intelligence. "
        "Tools are tiered: Free, Premium, and Analyst access levels."
    ),
    auth=KeycloakMCPVerifier(),
    middleware=[MCPAuthMiddleware(auth=finint_component_auth)],
)


# ---------------------------------------------------------------------------
# Custom routes
# ---------------------------------------------------------------------------

@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint for Docker and load balancers."""
    return JSONResponse({
        "status": "healthy",
        "service": "finint-mcp-server",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@mcp.custom_route("/.well-known/oauth-protected-resource", methods=["GET"])
async def protected_resource_metadata(request: Request) -> JSONResponse:
    """RFC 9728 Protected Resource Metadata for MCP OAuth discovery."""
    return JSONResponse({
        "resource": settings.oauth_resource_url,
        "authorization_servers": [settings.keycloak_issuer],
        "scopes_supported": ALL_SCOPES,
        "bearer_methods_supported": ["header"],
    })


@mcp.custom_route("/api/tools/catalog", methods=["GET"])
async def tool_catalog(request: Request) -> JSONResponse:
    """OpenAPI-style tool catalog — lists every tool with its scope, tier, and description."""
    free_scopes = set(TIER_SCOPES[TIER_FREE])
    premium_scopes = set(TIER_SCOPES[TIER_PREMIUM])

    tier_rank = {"free": 0, "premium": 1, "analyst": 2}

    def _min_tier(scope: str) -> str:
        if scope in free_scopes:
            return "free"
        if scope in premium_scopes:
            return "premium"
        return "analyst"

    def _min_tier_for_spec(spec: str | tuple[str, ...]) -> str:
        if isinstance(spec, str):
            return _min_tier(spec)
        tiers = [_min_tier(s) for s in spec]
        return max(tiers, key=lambda t: tier_rank[t])

    tools = []
    for tool_name, spec in sorted(TOOL_SCOPE_MAP.items()):
        scopes_req = list(tool_scope_specs(tool_name))
        tools.append({
            "name": tool_name,
            "endpoint": f"/api/tool/{tool_name}",
            "method": "POST",
            "required_scopes": scopes_req,
            "minimum_tier": _min_tier_for_spec(spec),
            "auth": "Bearer JWT (OAuth 2.1 + PKCE via Keycloak)",
        })

    return JSONResponse({
        "openapi": "3.1.0",
        "info": {
            "title": "FinInt MCP Server — Tool Catalog",
            "version": "1.0.0",
            "description": "Indian Financial Intelligence MCP Server. All tools require Bearer JWT authentication.",
        },
        "server": settings.oauth_resource_url,
        "tool_count": len(tools),
        "tiers": {
            "free": {"tools": sum(1 for t in tools if t["minimum_tier"] == "free"), "rate_limit": "30 calls/hr"},
            "premium": {"tools": sum(1 for t in tools if t["minimum_tier"] in ("free", "premium")), "rate_limit": "150 calls/hr"},
            "analyst": {"tools": len(tools), "rate_limit": "500 calls/hr"},
        },
        "tools": tools,
        "auth": {
            "type": "oauth2",
            "token_endpoint": f"{settings.keycloak_issuer}/protocol/openid-connect/token",
            "resource_metadata": f"{settings.oauth_resource_url}/.well-known/oauth-protected-resource",
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@mcp.custom_route("/api/status", methods=["GET"])
async def api_status(request: Request) -> JSONResponse:
    """Returns upstream API health and quota status."""
    return JSONResponse({
        "upstream_apis": {
            "angel_one": {"status": "configured" if settings.angel_one_api_key else "not_configured"},
            "mfapi": {"status": "available"},
            "bse": {"status": "available"},
            "finnhub": {"status": "configured" if settings.finnhub_key else "not_configured"},
            "alpha_vantage": {"status": "configured" if settings.alpha_vantage_key else "not_configured"},
            "gnews": {"status": "configured" if settings.gnews_key else "not_configured"},
            "rbi_dbie": {"status": "available"},
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# ---------------------------------------------------------------------------
# Tier upgrade request endpoints (admin workflow)
# ---------------------------------------------------------------------------

import uuid as _uuid

_tier_requests: list[dict] = []


@mcp.custom_route("/api/tier-request", methods=["POST"])
async def submit_tier_request(request: Request) -> JSONResponse:
    """User submits a tier upgrade request."""
    body = await request.json()
    requested_tier = body.get("requested_tier", "")
    if requested_tier not in ("premium", "analyst"):
        return JSONResponse({"error": "Invalid tier"}, status_code=400)

    auth_header = request.headers.get("Authorization", "")
    user_id = "anonymous"
    username = "anonymous"
    email = ""
    current_tier = "free"
    if auth_header.startswith("Bearer "):
        try:
            from .auth.provider import auth_provider
            claims = await auth_provider.validate_token(auth_header.split(" ", 1)[1])
            user_id = claims.sub
            username = claims.preferred_username or user_id
            email = claims.email or ""
            current_tier = claims.tier
        except Exception:
            pass

    req_id = str(_uuid.uuid4())
    _tier_requests.append({
        "id": req_id,
        "user_id": user_id,
        "username": username,
        "email": email,
        "current_tier": current_tier,
        "requested_tier": requested_tier,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    log.info("tier_request.submitted", user_id=user_id, requested_tier=requested_tier)
    return JSONResponse({"id": req_id, "status": "pending"}, status_code=201)


@mcp.custom_route("/api/admin/tier-requests", methods=["GET"])
async def list_tier_requests(request: Request) -> JSONResponse:
    """Admin lists all tier upgrade requests."""
    return JSONResponse({"requests": _tier_requests})


@mcp.custom_route("/api/admin/tier-requests/{request_id}/approve", methods=["POST"])
async def approve_tier_request(request: Request) -> JSONResponse:
    """Admin approves a tier upgrade request."""
    request_id = request.path_params.get("request_id", "")
    for req in _tier_requests:
        if req["id"] == request_id:
            req["status"] = "approved"
            req["reviewed_at"] = datetime.now(timezone.utc).isoformat()
            log.info("tier_request.approved", request_id=request_id, user_id=req["user_id"])
            return JSONResponse({"id": request_id, "status": "approved"})
    return JSONResponse({"error": "Not found"}, status_code=404)


@mcp.custom_route("/api/admin/tier-requests/{request_id}/reject", methods=["POST"])
async def reject_tier_request(request: Request) -> JSONResponse:
    """Admin rejects a tier upgrade request."""
    request_id = request.path_params.get("request_id", "")
    for req in _tier_requests:
        if req["id"] == request_id:
            req["status"] = "rejected"
            req["reviewed_at"] = datetime.now(timezone.utc).isoformat()
            log.info("tier_request.rejected", request_id=request_id, user_id=req["user_id"])
            return JSONResponse({"id": request_id, "status": "rejected"})
    return JSONResponse({"error": "Not found"}, status_code=404)


# ---------------------------------------------------------------------------
# REST bridge — allows frontend to call MCP tools via POST /api/tool/{name}
# ---------------------------------------------------------------------------

@mcp.custom_route("/api/tool/{tool_name}", methods=["POST"])
async def rest_tool_bridge(request: Request) -> JSONResponse:
    """REST bridge: POST /api/tool/<name> with JSON body → call MCP tool.

    Requires a valid Bearer JWT token. Returns 401 if missing/invalid,
    403 if the user's tier lacks the required scope, 429 if rate limited.
    """
    tool_name = request.path_params.get("tool_name", "")

    _rm = settings.oauth_resource_metadata_url
    _www_challenge = f'Bearer realm="finint", resource_metadata="{_rm}"'

    # --- AUTH: extract and validate JWT ---
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer ") or len(auth_header.split(" ", 1)) < 2:
        return JSONResponse(
            {"error": "Authentication required", "error_code": "UNAUTHORIZED"},
            status_code=401,
            headers={"WWW-Authenticate": _www_challenge},
        )
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        return JSONResponse(
            {"error": "Authentication required", "error_code": "UNAUTHORIZED"},
            status_code=401,
            headers={"WWW-Authenticate": _www_challenge},
        )

    try:
        claims = await _auth_provider.validate_token(token)
    except Exception as exc:
        log.warning("rest_bridge.auth_failed", tool=tool_name, error=str(exc))
        return JSONResponse(
            {"error": "Invalid or expired token", "error_code": "UNAUTHORIZED"},
            status_code=401,
            headers={
                "WWW-Authenticate": (
                    f'Bearer realm="finint", error="invalid_token", resource_metadata="{_rm}"'
                ),
            },
        )

    # --- SCOPE CHECK: does the user's tier allow this tool? ---
    if not _tier_filter.is_tool_allowed(tool_name, claims):
        reqs = tool_scope_specs(tool_name)
        scope_hint = " ".join(reqs) if reqs else "unknown"
        log.info("rest_bridge.forbidden", tool=tool_name, tier=claims.tier, required=reqs)
        return JSONResponse(
            {
                "error": f"Insufficient scope for tool '{tool_name}'",
                "error_code": "FORBIDDEN",
                "required_scopes": list(reqs),
                "user_tier": claims.tier,
                "hint": "Upgrade your tier to access this tool.",
            },
            status_code=403,
            headers={
                "WWW-Authenticate": (
                    f'Bearer realm="finint", error="insufficient_scope", '
                    f'resource_metadata="{_rm}", scope="{scope_hint}"'
                ),
            },
        )

    # --- RATE LIMIT CHECK (best-effort) ---
    rl = await _get_rate_limiter()
    if rl is not None:
        try:
            rate_result = await rl.check_rate_limit(claims.user_id, claims.tier)
            if not rate_result.allowed:
                return JSONResponse(
                    {
                        "error": "Rate limit exceeded",
                        "error_code": "RATE_LIMITED",
                        "retry_after": rate_result.retry_after,
                    },
                    status_code=429,
                    headers={"Retry-After": str(rate_result.retry_after or 60)},
                )
        except Exception as exc:
            log.warning("rate_limit_check_failed", error=str(exc))

    # --- AUDIT LOG (best-effort) ---
    await _ensure_audit_logger()
    try:
        await _audit_logger.log_tool_call(
            user_id=claims.user_id, tier=claims.tier, tool_name=tool_name,
        )
    except Exception as exc:
        log.warning("audit_log_failed", error=str(exc))

    # --- CALL TOOL ---
    try:
        body = await request.json()
    except Exception:
        body = {}

    # Auto-inject authenticated user_id for portfolio tools (per-user isolation)
    _PORTFOLIO_TOOLS = {
        "add_to_portfolio", "remove_from_portfolio", "get_portfolio_summary",
        "portfolio_health_check", "check_concentration_risk", "check_mf_overlap",
        "check_macro_sensitivity", "detect_sentiment_shift", "portfolio_risk_report",
        "what_if_analysis", "import_portfolio",
    }
    if isinstance(body, dict) and tool_name in _PORTFOLIO_TOOLS:
        body["user_id"] = claims.user_id

    try:
        result = await mcp.call_tool(tool_name, body)
        # Extract text from ToolResult content
        parts = []
        for item in result.content:
            if hasattr(item, "text"):
                parts.append(item.text)
        combined = parts[0] if len(parts) == 1 else "\n".join(parts)
        # Try to parse as JSON
        import json as _json
        try:
            parsed = _json.loads(combined)
            return JSONResponse(parsed)
        except (ValueError, TypeError):
            return JSONResponse({"data": combined})
    except Exception as exc:
        if "Unknown tool" in str(exc):
            return JSONResponse({"error": f"Unknown tool: {tool_name}"}, status_code=404)
        log.error("rest_bridge.error", tool=tool_name, error=str(exc))
        return JSONResponse({"error": str(exc)}, status_code=500)


@mcp.custom_route("/api/resource", methods=["GET"])
async def rest_resource_bridge(request: Request) -> JSONResponse:
    """REST bridge: GET /api/resource?uri=<uri> → read MCP resource.

    Requires a valid Bearer JWT token.
    """
    _rm = settings.oauth_resource_metadata_url
    _www_challenge = f'Bearer realm="finint", resource_metadata="{_rm}"'

    # --- AUTH ---
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer ") or len(auth_header.split(" ", 1)) < 2:
        return JSONResponse(
            {"error": "Authentication required", "error_code": "UNAUTHORIZED"},
            status_code=401,
            headers={"WWW-Authenticate": _www_challenge},
        )
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        return JSONResponse(
            {"error": "Authentication required", "error_code": "UNAUTHORIZED"},
            status_code=401,
            headers={"WWW-Authenticate": _www_challenge},
        )
    try:
        claims = await _auth_provider.validate_token(token)
    except Exception as exc:
        log.warning("rest_resource.auth_failed", error=str(exc))
        return JSONResponse(
            {"error": "Invalid or expired token", "error_code": "UNAUTHORIZED"},
            status_code=401,
            headers={
                "WWW-Authenticate": (
                    f'Bearer realm="finint", error="invalid_token", resource_metadata="{_rm}"'
                ),
            },
        )

    uri = request.query_params.get("uri", "")
    if not uri:
        return JSONResponse({"error": "Missing 'uri' query parameter"}, status_code=400)

    try:
        result = await mcp.read_resource(uri)
        if isinstance(result, str):
            try:
                return JSONResponse(json.loads(result))
            except (json.JSONDecodeError, TypeError):
                return JSONResponse({"data": result})
        return JSONResponse({"data": result})
    except Exception as exc:
        log.error("rest_resource.error", uri=uri, error=str(exc))
        return JSONResponse({"error": str(exc)}, status_code=500)


# ---------------------------------------------------------------------------
# Tool registration imports (loaded at module level so FastMCP discovers them)
# ---------------------------------------------------------------------------

def _register_tools() -> None:
    """Import all tool modules to register them with the MCP server."""
    from .tools.market import tools as _market  # noqa: F401
    from .tools.fundamentals import tools as _fund  # noqa: F401
    from .tools.mutual_funds import tools as _mf  # noqa: F401
    from .tools.news import tools as _news  # noqa: F401
    from .tools.macro import tools as _macro  # noqa: F401
    from .tools.filings import tools as _filings  # noqa: F401
    from .tools.portfolio import tools as _portfolio  # noqa: F401
    from .tools.earnings import tools as _earnings  # noqa: F401
    from .tools.cross_source import tools as _cross  # noqa: F401
    from .resources import resources as _resources  # noqa: F401
    from .prompts import prompts as _prompts  # noqa: F401


_register_tools()

# Initialise LangSmith tracing (OpenTelemetry + OpenInference)
init_tracing()


# ---------------------------------------------------------------------------
# ASGI application with CORS for browser-based MCP clients
# ---------------------------------------------------------------------------

cors_middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=[
            "mcp-protocol-version",
            "mcp-session-id",
            "Authorization",
            "Content-Type",
        ],
        expose_headers=["mcp-session-id"],
    )
]

app = mcp.http_app(path="/mcp", middleware=cors_middleware)


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    log.info(
        "starting_mcp_server",
        host=settings.mcp_server_host,
        port=settings.mcp_server_port,
    )
    uvicorn.run(
        "src.server:app",
        host=settings.mcp_server_host,
        port=settings.mcp_server_port,
        reload=True,
    )
