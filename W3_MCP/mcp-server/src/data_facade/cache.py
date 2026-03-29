"""Dual-layer cache: L1 in-memory LRU + L2 Redis."""

from __future__ import annotations

import asyncio
import random
import time
from typing import Any

import redis.asyncio as aioredis
import structlog
from cachetools import LRUCache

from ..config.constants import L1_CACHE_MAX_SIZE, TTL_JITTER_PERCENT
from ..config.settings import settings

logger = structlog.get_logger(__name__)


class DualCache:
    """L1 (in-memory LRU) → L2 (Redis) two-tier cache.

    Supports stale-while-revalidate: callers can request stale data
    from a parallel shadow key while a background refresh runs.
    """

    def __init__(self) -> None:
        self._l1: LRUCache = LRUCache(maxsize=L1_CACHE_MAX_SIZE)
        self._l1_ts: dict[str, float] = {}
        self._redis: aioredis.Redis | None = None

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
            )
        return self._redis

    @staticmethod
    def _key(data_type: str, identifier: str) -> str:
        return f"finint:{data_type}:{identifier}"

    @staticmethod
    def _stale_key(key: str) -> str:
        return f"{key}:stale"

    @staticmethod
    def _apply_jitter(ttl: int) -> int:
        jitter = ttl * TTL_JITTER_PERCENT / 100
        return max(1, int(ttl + random.uniform(-jitter, jitter)))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get(self, data_type: str, identifier: str) -> Any | None:
        key = self._key(data_type, identifier)

        value = self._l1.get(key)
        if value is not None:
            logger.debug("cache.l1.hit", key=key)
            return value

        try:
            r = await self._get_redis()
            import json

            raw = await r.get(key)
            if raw is not None:
                logger.debug("cache.l2.hit", key=key)
                value = json.loads(raw)
                self._l1[key] = value
                self._l1_ts[key] = time.monotonic()
                return value
        except Exception:
            logger.warning("cache.l2.error", key=key, exc_info=True)

        logger.debug("cache.miss", key=key)
        return None

    async def set(
        self, data_type: str, identifier: str, value: Any, ttl: int = 60
    ) -> None:
        key = self._key(data_type, identifier)
        jittered_ttl = self._apply_jitter(ttl)

        self._l1[key] = value
        self._l1_ts[key] = time.monotonic()

        try:
            import json

            r = await self._get_redis()
            pipe = r.pipeline()
            serialized = json.dumps(value, default=str)
            pipe.set(key, serialized, ex=jittered_ttl)
            stale_ttl = jittered_ttl * 3
            pipe.set(self._stale_key(key), serialized, ex=stale_ttl)
            await pipe.execute()
            logger.debug("cache.set", key=key, ttl=jittered_ttl)
        except Exception:
            logger.warning("cache.l2.set_error", key=key, exc_info=True)

    async def get_stale(self, data_type: str, identifier: str) -> Any | None:
        """Return stale (expired-but-preserved) data for revalidation."""
        key = self._stale_key(self._key(data_type, identifier))

        try:
            import json

            r = await self._get_redis()
            raw = await r.get(key)
            if raw is not None:
                logger.debug("cache.stale.hit", key=key)
                return json.loads(raw)
        except Exception:
            logger.warning("cache.stale.error", key=key, exc_info=True)
        return None

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None


dual_cache = DualCache()
