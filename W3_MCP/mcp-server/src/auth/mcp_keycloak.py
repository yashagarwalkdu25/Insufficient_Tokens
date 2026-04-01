"""FastMCP streamable HTTP: Keycloak JWT + tier-derived scopes (matches REST bridge)."""

from __future__ import annotations

import structlog
from fastmcp.prompts.base import Prompt
from fastmcp.resources.base import Resource
from fastmcp.server.auth import AccessToken, AuthContext
from fastmcp.server.auth.auth import TokenVerifier
from fastmcp.tools.base import Tool

from ..config.constants import (
    SCOPE_FILINGS_DEEP,
    SCOPE_FUNDAMENTALS_READ,
    SCOPE_MACRO_READ,
    SCOPE_MARKET_READ,
    SCOPE_NEWS_READ,
    SCOPE_PORTFOLIO_READ,
    SCOPE_RESEARCH_GENERATE,
    SCOPE_TECHNICALS_READ,
    SCOPE_WATCHLIST_READ,
)
from ..config.settings import settings
from .middleware import tool_scope_specs
from .provider import KeycloakAuthProvider

logger = structlog.get_logger(__name__)

# Minimum scopes to list/get a prompt (PDF PS1/PS2/PS3 tier addenda).
PROMPT_SCOPE_MAP: dict[str, tuple[str, ...]] = {
    "quick_analysis": (SCOPE_MARKET_READ, SCOPE_NEWS_READ),
    "deep_dive": (
        SCOPE_FUNDAMENTALS_READ,
        SCOPE_TECHNICALS_READ,
        SCOPE_NEWS_READ,
        SCOPE_MACRO_READ,
    ),
    "sector_scan": (SCOPE_FUNDAMENTALS_READ, SCOPE_NEWS_READ),
    "morning_brief": (SCOPE_MARKET_READ, SCOPE_NEWS_READ, SCOPE_MACRO_READ),
    "morning_risk_brief": (SCOPE_PORTFOLIO_READ, SCOPE_NEWS_READ, SCOPE_MACRO_READ),
    "rebalance_suggestions": (SCOPE_PORTFOLIO_READ,),
    "earnings_exposure": (SCOPE_FUNDAMENTALS_READ, SCOPE_MARKET_READ),
    "earnings_preview": (SCOPE_FUNDAMENTALS_READ,),
    "results_flash": (SCOPE_FUNDAMENTALS_READ,),
    "sector_earnings_recap": (SCOPE_RESEARCH_GENERATE,),
    "earnings_surprise_scan": (SCOPE_RESEARCH_GENERATE,),
}


def _resource_required_scopes(uri: str) -> tuple[str, ...] | None:
    """Scopes that must all be present; None = unknown URI (deny)."""
    if uri.startswith("market://overview"):
        return (SCOPE_MARKET_READ,)
    if uri.startswith("macro://snapshot"):
        return (SCOPE_MACRO_READ,)
    if uri.startswith("watchlist://"):
        return (SCOPE_WATCHLIST_READ,)
    if uri.startswith("research://"):
        return (SCOPE_RESEARCH_GENERATE,)
    if uri.startswith("portfolio://"):
        if "/alerts" in uri or "/risk_score" in uri:
            return (SCOPE_PORTFOLIO_READ,)
        return (SCOPE_WATCHLIST_READ,)
    if uri.startswith("earnings://calendar"):
        return (SCOPE_MARKET_READ,)
    if uri.startswith("earnings://"):
        if "/history" in uri:
            return (SCOPE_FUNDAMENTALS_READ,)
        if "/latest" in uri:
            return (SCOPE_FILINGS_DEEP,)
        return (SCOPE_MARKET_READ,)
    if uri.startswith("filing://"):
        return (SCOPE_FILINGS_DEEP,)
    return None


def finint_component_auth(ctx: AuthContext) -> bool:
    """Tier-aware visibility and invocation for tools, prompts, and resources."""
    if ctx.token is None:
        return False
    user = set(ctx.token.scopes)
    comp = ctx.component
    if comp is None:
        return True

    if isinstance(comp, Tool):
        reqs = tool_scope_specs(comp.name)
        if not reqs:
            logger.warning("mcp_tool_unmapped", tool=comp.name)
            return False
        return all(s in user for s in reqs)

    if isinstance(comp, Prompt):
        reqs = PROMPT_SCOPE_MAP.get(comp.name)
        if reqs is None:
            logger.warning("mcp_prompt_unmapped", prompt=comp.name)
            return False
        return all(s in user for s in reqs)

    if isinstance(comp, Resource):
        reqs = _resource_required_scopes(comp.uri)
        if reqs is None:
            logger.warning("mcp_resource_unmapped", uri=comp.uri)
            return False
        return all(s in user for s in reqs)

    return True


class KeycloakMCPVerifier(TokenVerifier):
    """Validate Keycloak JWTs; attach tier-derived FinInt scopes (same as REST bridge)."""

    def __init__(self) -> None:
        super().__init__(base_url=settings.oauth_resource_url, required_scopes=None)
        self._kc = KeycloakAuthProvider()

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            c = await self._kc.validate_token(token)
        except Exception as exc:
            logger.debug("mcp_jwt_rejected", error=str(exc))
            return None

        exp_raw = c.raw_jwt_claims.get("exp")
        exp_int: int | None = int(exp_raw) if isinstance(exp_raw, (int, float)) else None

        return AccessToken(
            token=token,
            client_id=c.user_id or "unknown",
            scopes=list(c.scopes),
            expires_at=exp_int,
            claims=c.raw_jwt_claims,
        )
