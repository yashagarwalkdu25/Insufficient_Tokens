"""PostgreSQL repository for portfolio holdings (per-user persistence)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog

from .pool import get_pool

logger = structlog.get_logger(__name__)

_ENSURE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS portfolio_holdings (
    id         SERIAL PRIMARY KEY,
    user_id    TEXT        NOT NULL,
    symbol     VARCHAR(50) NOT NULL,
    quantity   INTEGER     NOT NULL,
    avg_price  NUMERIC(12,2) NOT NULL,
    added_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, symbol)
);
CREATE INDEX IF NOT EXISTS idx_portfolio_user ON portfolio_holdings(user_id);
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
        logger.info("portfolio_repo.table_ready")
    except Exception as exc:
        logger.error("portfolio_repo.init_failed", error=str(exc))


async def get_holdings(user_id: str) -> list[dict[str, Any]]:
    """Return all holdings for a user from PostgreSQL."""
    await _ensure_table()
    try:
        pool = await get_pool()
        rows = await pool.fetch(
            "SELECT symbol, quantity, avg_price FROM portfolio_holdings WHERE user_id = $1 ORDER BY symbol",
            user_id,
        )
        return [{"symbol": r["symbol"], "quantity": r["quantity"], "avg_price": float(r["avg_price"])} for r in rows]
    except Exception as exc:
        logger.error("portfolio_repo.get_failed", user_id=user_id, error=str(exc))
        return []


async def upsert_holding(user_id: str, symbol: str, quantity: int, avg_price: float) -> None:
    """Insert or update a single holding for a user."""
    await _ensure_table()
    try:
        pool = await get_pool()
        await pool.execute(
            """
            INSERT INTO portfolio_holdings (user_id, symbol, quantity, avg_price, updated_at)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (user_id, symbol)
            DO UPDATE SET quantity = $3, avg_price = $4, updated_at = $5
            """,
            user_id, symbol, quantity, avg_price, datetime.now(timezone.utc),
        )
    except Exception as exc:
        logger.error("portfolio_repo.upsert_failed", user_id=user_id, symbol=symbol, error=str(exc))


async def remove_holding(user_id: str, symbol: str) -> None:
    """Remove a holding for a user."""
    await _ensure_table()
    try:
        pool = await get_pool()
        await pool.execute(
            "DELETE FROM portfolio_holdings WHERE user_id = $1 AND symbol = $2",
            user_id, symbol,
        )
    except Exception as exc:
        logger.error("portfolio_repo.remove_failed", user_id=user_id, symbol=symbol, error=str(exc))


async def bulk_upsert(user_id: str, holdings: list[dict[str, Any]]) -> None:
    """Upsert multiple holdings in a single transaction."""
    await _ensure_table()
    try:
        pool = await get_pool()
        now = datetime.now(timezone.utc)
        async with pool.acquire() as conn:
            async with conn.transaction():
                for h in holdings:
                    await conn.execute(
                        """
                        INSERT INTO portfolio_holdings (user_id, symbol, quantity, avg_price, updated_at)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (user_id, symbol)
                        DO UPDATE SET quantity = $3, avg_price = $4, updated_at = $5
                        """,
                        user_id, h["symbol"], h["quantity"], h["avg_price"], now,
                    )
    except Exception as exc:
        logger.error("portfolio_repo.bulk_upsert_failed", user_id=user_id, error=str(exc))
