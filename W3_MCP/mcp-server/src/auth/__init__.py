"""Authentication, authorization, rate-limiting, and audit subsystem."""

from __future__ import annotations

from .provider import KeycloakAuthProvider, TokenClaims
from .middleware import check_scope, get_user_tier, TierToolFilter, TOOL_SCOPE_MAP
from .rate_limiter import RateLimiter, RateLimitResult
from .audit import AuditLogger

__all__ = [
    "KeycloakAuthProvider",
    "TokenClaims",
    "check_scope",
    "get_user_tier",
    "TierToolFilter",
    "TOOL_SCOPE_MAP",
    "RateLimiter",
    "RateLimitResult",
    "AuditLogger",
]
