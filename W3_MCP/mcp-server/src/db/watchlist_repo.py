"""PostgreSQL repository for user watchlists (per-user persistence)."""
from __future__ import annotations

from typing import Any

import structlog

from .pool import get_pool

logger = structlog.get_logger(__name__)

_ENSURE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS user_watchlists (
    id       SERIAL PRIMARY KEY,
    user_id  TEXT        NOT NULL,
    symbol   VARCHAR(50) NOT NULL,
    added_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, symbol)
);
CREATE INDEX IF NOT EXISTS idx_watchlist_user ON user_watchlists(user_id);
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
        logger.info("watchlist_repo.table_ready")
    except Exception as exc:
        logger.error("watchlist_repo.init_failed", error=str(exc))


async def get_watchlist(user_id: str) -> list[str]:
    """Return all watchlist symbols for a user."""
    await _ensure_table()
    try:
        pool = await get_pool()
        rows = await pool.fetch(
            "SELECT symbol FROM user_watchlists WHERE user_id = $1 ORDER BY symbol",
            user_id,
        )
        return [r["symbol"] for r in rows]
    except Exception as exc:
        logger.error("watchlist_repo.get_failed", user_id=user_id, error=str(exc))
        return []


async def add_symbol(user_id: str, symbol: str) -> None:
    """Add a symbol to a user's watchlist."""
    await _ensure_table()
    try:
        pool = await get_pool()
        await pool.execute(
            """
            INSERT INTO user_watchlists (user_id, symbol)
            VALUES ($1, $2)
            ON CONFLICT (user_id, symbol) DO NOTHING
            """,
            user_id, symbol,
        )
    except Exception as exc:
        logger.error("watchlist_repo.add_failed", user_id=user_id, symbol=symbol, error=str(exc))


async def remove_symbol(user_id: str, symbol: str) -> None:
    """Remove a symbol from a user's watchlist."""
    await _ensure_table()
    try:
        pool = await get_pool()
        await pool.execute(
            "DELETE FROM user_watchlists WHERE user_id = $1 AND symbol = $2",
            user_id, symbol,
        )
    except Exception as exc:
        logger.error("watchlist_repo.remove_failed", user_id=user_id, symbol=symbol, error=str(exc))


async def set_watchlist(user_id: str, symbols: list[str]) -> None:
    """Replace the entire watchlist for a user."""
    await _ensure_table()
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "DELETE FROM user_watchlists WHERE user_id = $1", user_id,
                )
                for sym in symbols:
                    await conn.execute(
                        """
                        INSERT INTO user_watchlists (user_id, symbol)
                        VALUES ($1, $2)
                        ON CONFLICT (user_id, symbol) DO NOTHING
                        """,
                        user_id, sym,
                    )
    except Exception as exc:
        logger.error("watchlist_repo.set_failed", user_id=user_id, error=str(exc))
