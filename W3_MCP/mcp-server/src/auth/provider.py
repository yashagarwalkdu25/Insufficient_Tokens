"""Keycloak JWT authentication provider with JWKS caching."""

from __future__ import annotations

import time
from typing import Any

import httpx
import jwt
import structlog
from jwt import PyJWKClient, PyJWKClientError
from pydantic import BaseModel, Field

from ..config.settings import settings
from ..config.constants import TIER_FREE, TIER_PREMIUM, TIER_ANALYST, TIER_SCOPES

logger = structlog.get_logger(__name__)

_TIER_PRIORITY = {TIER_ANALYST: 3, TIER_PREMIUM: 2, TIER_FREE: 1}
_JWKS_CACHE_TTL = 3600  # 1 hour


class TokenClaims(BaseModel):
    """Validated claims extracted from a Keycloak JWT."""

    user_id: str
    username: str
    tier: str
    scopes: list[str] = Field(default_factory=list)
    email: str = ""


class KeycloakAuthProvider:
    """Validates JWTs issued by Keycloak and extracts tier-based claims."""

    def __init__(self) -> None:
        self._issuer: str = settings.keycloak_issuer
        self._audience: str = settings.keycloak_client_id
        self._jwks_uri: str = settings.keycloak_jwks_uri

        self._jwks_client: PyJWKClient | None = None
        self._jwks_cache: dict[str, Any] = {}
        self._jwks_fetched_at: float = 0.0

    async def _ensure_jwks(self, *, force: bool = False) -> None:
        """Fetch JWKS from Keycloak and cache the keys for reuse."""
        now = time.monotonic()
        if (
            not force
            and self._jwks_client is not None
            and (now - self._jwks_fetched_at) < _JWKS_CACHE_TTL
        ):
            return

        logger.info("jwks_fetch", uri=self._jwks_uri, force=force)
        self._jwks_client = PyJWKClient(
            self._jwks_uri,
            cache_jwk_set=True,
            lifespan=_JWKS_CACHE_TTL,
        )
        self._jwks_fetched_at = now

    async def _fetch_jwks_raw(self) -> dict[str, Any]:
        """Fetch raw JWKS JSON (used as fallback for manual kid lookup)."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(self._jwks_uri)
            resp.raise_for_status()
            return resp.json()

    def _resolve_tier(self, realm_roles: list[str]) -> str:
        """Pick the highest-priority tier from realm_access.roles."""
        best_tier = TIER_FREE
        best_priority = 0
        for role in realm_roles:
            p = _TIER_PRIORITY.get(role, 0)
            if p > best_priority:
                best_priority = p
                best_tier = role
        return best_tier

    async def validate_token(self, token: str) -> TokenClaims:
        """Validate a Keycloak JWT and return structured claims.

        Raises ``jwt.InvalidTokenError`` (or subclass) on any failure.
        """
        await self._ensure_jwks()
        assert self._jwks_client is not None

        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
        except PyJWKClientError:
            logger.warning("jwks_kid_mismatch", action="refreshing")
            await self._ensure_jwks(force=True)
            assert self._jwks_client is not None
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)

        payload: dict[str, Any] = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=self._issuer,
            audience=self._audience,
            options={
                "verify_exp": True,
                "verify_iss": True,
                "verify_aud": True,
            },
        )

        realm_access: dict[str, Any] = payload.get("realm_access", {})
        realm_roles: list[str] = realm_access.get("roles", [])

        tier = self._resolve_tier(realm_roles)
        scopes = TIER_SCOPES.get(tier, TIER_SCOPES[TIER_FREE])

        claims = TokenClaims(
            user_id=payload.get("sub", ""),
            username=payload.get("preferred_username", ""),
            tier=tier,
            scopes=scopes,
            email=payload.get("email", ""),
        )

        logger.info(
            "token_validated",
            user_id=claims.user_id,
            username=claims.username,
            tier=claims.tier,
        )
        return claims
