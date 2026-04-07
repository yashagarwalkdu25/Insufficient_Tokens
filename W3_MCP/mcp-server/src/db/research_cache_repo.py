"""PostgreSQL repository for caching CrewAI research/risk/earnings results."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import structlog

from .pool import get_pool

logger = structlog.get_logger(__name__)

_ENSURE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS research_results_cache (
    id          SERIAL PRIMARY KEY,
    cache_key   VARCHAR(255) UNIQUE NOT NULL,
    crew_type   VARCHAR(50) NOT NULL,
    symbol      VARCHAR(50),
    user_id     TEXT,
    result_json JSONB       NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_research_cache_key ON research_results_cache(cache_key);
CREATE INDEX IF NOT EXISTS idx_research_cache_expires ON research_results_cache(expires_at);
"""

_initialised = False


async def _ensure_table() -> None:
    global _initialised
    if _initialised:
        return
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(_ENSURE_TABLES_SQL)
        _initialised = True
        logger.info("research_cache_repo.table_ready")
    except Exception as exc:
        logger.error("research_cache_repo.init_failed", error=str(exc))


async def get_cached(cache_key: str) -> dict[str, Any] | None:
    """Return cached result if it exists and hasn't expired."""
    await _ensure_table()
    try:
        pool = await get_pool()
        row = await pool.fetchrow(
            """
            SELECT result_json FROM research_results_cache
            WHERE cache_key = $1 AND expires_at > NOW()
            """,
            cache_key,
        )
        if row:
            result = row["result_json"]
            if isinstance(result, str):
                return json.loads(result)
            return dict(result)
        return None
    except Exception as exc:
        logger.error("research_cache_repo.get_failed", key=cache_key, error=str(exc))
        return None


async def set_cached(
    cache_key: str,
    crew_type: str,
    result: dict[str, Any],
    ttl_seconds: int = 3600,
    symbol: str | None = None,
    user_id: str | None = None,
) -> None:
    """Cache a CrewAI result with TTL."""
    await _ensure_table()
    try:
        pool = await get_pool()
        now = datetime.now(timezone.utc)
        from datetime import timedelta
        expires = now + timedelta(seconds=ttl_seconds)
        result_json = json.dumps(result, default=str)
        await pool.execute(
            """
            INSERT INTO research_results_cache (cache_key, crew_type, symbol, user_id, result_json, created_at, expires_at)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7)
            ON CONFLICT (cache_key)
            DO UPDATE SET result_json = $5::jsonb, created_at = $6, expires_at = $7
            """,
            cache_key, crew_type, symbol, user_id, result_json, now, expires,
        )
    except Exception as exc:
        logger.error("research_cache_repo.set_failed", key=cache_key, error=str(exc))


async def invalidate(cache_key: str) -> None:
    """Remove a specific cache entry."""
    await _ensure_table()
    try:
        pool = await get_pool()
        await pool.execute("DELETE FROM research_results_cache WHERE cache_key = $1", cache_key)
    except Exception as exc:
        logger.error("research_cache_repo.invalidate_failed", key=cache_key, error=str(exc))


async def cleanup_expired() -> int:
    """Remove all expired cache entries. Returns count deleted."""
    await _ensure_table()
    try:
        pool = await get_pool()
        result = await pool.execute("DELETE FROM research_results_cache WHERE expires_at < NOW()")
        return int(result.split(" ")[-1]) if result else 0
    except Exception as exc:
        logger.error("research_cache_repo.cleanup_failed", error=str(exc))
        return 0
