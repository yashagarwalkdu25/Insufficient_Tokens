"""Redis-backed sliding window rate limiter with upstream quota tracking."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel

from ..config.settings import settings
from ..config.constants import (
    TIER_RATE_LIMITS,
    TIER_FREE,
    RATE_LIMIT_WINDOW_SECONDS,
    QUOTA_ALPHA_VANTAGE_DAILY,
    QUOTA_GNEWS_DAILY,
)

if TYPE_CHECKING:
    import redis.asyncio as aioredis

logger = structlog.get_logger(__name__)

_UPSTREAM_DAILY_LIMITS: dict[str, int] = {
    "alpha_vantage": QUOTA_ALPHA_VANTAGE_DAILY,
    "gnews": QUOTA_GNEWS_DAILY,
}


class RateLimitResult(BaseModel):
    """Outcome of a rate-limit check."""

    allowed: bool
    remaining: int
    reset_at: datetime
    retry_after: int | None = None


class RateLimiter:
    """Sliding-window counter rate limiter backed by Redis."""

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    async def check_rate_limit(self, user_id: str, tier: str) -> RateLimitResult:
        """Check (and increment) the sliding-window counter for *user_id*."""
        limit = TIER_RATE_LIMITS.get(tier, TIER_RATE_LIMITS[TIER_FREE])
        window = RATE_LIMIT_WINDOW_SECONDS

        now = datetime.now(tz=timezone.utc)
        window_start = int(now.timestamp()) // window * window
        window_end = window_start + window
        reset_at = datetime.fromtimestamp(window_end, tz=timezone.utc)

        key = f"rate:{user_id}:{window_start}"

        pipe = self._redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, window + 60)  # TTL slightly longer than the window
        results = await pipe.execute()
        current_count: int = results[0]

        remaining = max(0, limit - current_count)
        allowed = current_count <= limit

        if not allowed:
            retry_after = window_end - int(now.timestamp())
            logger.warning(
                "rate_limit_exceeded",
                user_id=user_id,
                tier=tier,
                count=current_count,
                limit=limit,
            )
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_at=reset_at,
                retry_after=retry_after,
            )

        logger.debug(
            "rate_limit_ok",
            user_id=user_id,
            tier=tier,
            remaining=remaining,
        )
        return RateLimitResult(
            allowed=True,
            remaining=remaining,
            reset_at=reset_at,
        )

    # ------------------------------------------------------------------
    # Upstream API quota helpers
    # ------------------------------------------------------------------

    async def check_upstream_quota(self, source: str) -> bool:
        """Return True if the daily quota for *source* has NOT been exhausted."""
        date_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        key = f"quota:{source}:{date_str}"

        current = await self._redis.get(key)
        count = int(current) if current else 0
        limit = _UPSTREAM_DAILY_LIMITS.get(source, 0)

        if limit == 0:
            return True

        allowed = count < limit
        if not allowed:
            logger.warning(
                "upstream_quota_exhausted",
                source=source,
                count=count,
                limit=limit,
            )
        return allowed

    async def increment_upstream_quota(self, source: str) -> None:
        """Increment the daily counter for *source* by 1."""
        date_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        key = f"quota:{source}:{date_str}"

        pipe = self._redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, 86_400 + 3600)  # auto-expire slightly after midnight
        await pipe.execute()

        logger.debug("upstream_quota_incremented", source=source, key=key)
