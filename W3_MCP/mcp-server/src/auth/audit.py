"""PostgreSQL-backed audit logger for MCP tool invocations."""

from __future__ import annotations

from typing import Any

import asyncpg
import structlog

from ..config.settings import settings

logger = structlog.get_logger(__name__)

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS audit_log (
    id              BIGSERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ NOT NULL DEFAULT now(),
    user_id         TEXT        NOT NULL,
    tier            TEXT        NOT NULL,
    tool_name       TEXT        NOT NULL,
    latency_ms      INTEGER,
    cache_hit       BOOLEAN     NOT NULL DEFAULT FALSE,
    source_used     TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_user_ts
    ON audit_log (user_id, ts DESC);

CREATE INDEX IF NOT EXISTS idx_audit_tool_ts
    ON audit_log (tool_name, ts DESC);
"""


class AuditLogger:
    """Async audit logger that writes tool-call records to PostgreSQL."""

    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None

    async def init(self) -> None:
        """Create the connection pool and ensure the audit table exists."""
        self._pool = await asyncpg.create_pool(
            dsn=settings.postgres_async_dsn,
            min_size=2,
            max_size=10,
        )
        async with self._pool.acquire() as conn:
            await conn.execute(_CREATE_TABLE_SQL)

        logger.info("audit_logger_ready")

    async def close(self) -> None:
        """Gracefully close the connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def log_tool_call(
        self,
        user_id: str,
        tier: str,
        tool_name: str,
        latency_ms: int | None = None,
        cache_hit: bool = False,
        source_used: str | None = None,
    ) -> None:
        """Insert a single audit record for a tool invocation."""
        if self._pool is None:
            logger.error("audit_pool_not_initialised")
            return

        try:
            await self._pool.execute(
                """
                INSERT INTO audit_log (user_id, tier, tool_name, latency_ms, cache_hit, source_used)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                user_id,
                tier,
                tool_name,
                latency_ms,
                cache_hit,
                source_used,
            )
        except Exception:
            logger.exception("audit_insert_failed", tool=tool_name, user=user_id)

    async def get_user_usage(
        self,
        user_id: str,
        hours: int = 24,
    ) -> list[dict[str, Any]]:
        """Return recent audit rows for *user_id* within the last *hours*."""
        if self._pool is None:
            logger.error("audit_pool_not_initialised")
            return []

        rows = await self._pool.fetch(
            """
            SELECT tool_name,
                   COUNT(*)            AS call_count,
                   AVG(latency_ms)     AS avg_latency_ms,
                   SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END) AS cache_hits
            FROM   audit_log
            WHERE  user_id = $1
              AND  ts >= now() - make_interval(hours => $2)
            GROUP  BY tool_name
            ORDER  BY call_count DESC
            """,
            user_id,
            hours,
        )
        return [dict(r) for r in rows]
