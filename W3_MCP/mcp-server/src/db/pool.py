"""Shared asyncpg connection pool — singleton for the MCP server."""
from __future__ import annotations

import asyncpg
import structlog

from ..config.settings import settings

logger = structlog.get_logger(__name__)

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Return (and lazily create) the shared asyncpg connection pool."""
    global _pool
    if _pool is not None:
        return _pool
    _pool = await asyncpg.create_pool(
        dsn=settings.postgres_async_dsn,
        min_size=2,
        max_size=10,
    )
    logger.info("db_pool_ready")
    return _pool


async def close_pool() -> None:
    """Gracefully close the shared pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("db_pool_closed")
