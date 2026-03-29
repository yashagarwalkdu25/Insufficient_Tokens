"""RBI DBIE adapter for macroeconomic data snapshots."""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_DEFAULT_MACRO: dict[str, Any] = {
    "repo_rate": 6.50,
    "reverse_repo_rate": 3.35,
    "cpi_inflation_pct": 4.75,
    "wpi_inflation_pct": 1.25,
    "gdp_growth_pct": 6.50,
    "forex_reserves_usd_bn": 640.0,
    "usd_inr": 83.50,
    "bank_rate": 6.75,
    "crr_pct": 4.50,
    "slr_pct": 18.00,
    "as_of": "2026-03-01",
}


class RBIDBIEAdapter:
    """Serves macroeconomic data from RBI DBIE.

    Keeps a hardcoded fallback snapshot and supports loading fresher
    values from PostgreSQL at startup.
    """

    def __init__(self) -> None:
        self._macro: dict[str, Any] = dict(_DEFAULT_MACRO)
        self._inflation_history: list[dict[str, Any]] = []

    async def get_macro_snapshot(self) -> dict[str, Any]:
        """Return the latest macro data snapshot."""
        try:
            return {
                "repo_rate": self._macro["repo_rate"],
                "cpi_inflation_pct": self._macro["cpi_inflation_pct"],
                "wpi_inflation_pct": self._macro["wpi_inflation_pct"],
                "gdp_growth_pct": self._macro["gdp_growth_pct"],
                "forex_reserves_usd_bn": self._macro["forex_reserves_usd_bn"],
                "usd_inr": self._macro["usd_inr"],
                "bank_rate": self._macro["bank_rate"],
                "crr_pct": self._macro["crr_pct"],
                "slr_pct": self._macro["slr_pct"],
                "as_of": self._macro["as_of"],
                "_source": "rbi_dbie",
            }
        except Exception as exc:
            logger.error("rbi_dbie.snapshot.error", error=str(exc))
            return {"error": str(exc), "error_code": "RBI_SNAPSHOT_FAILED", "_source": "rbi_dbie"}

    async def get_inflation_history(self, months: int = 12) -> dict[str, Any]:
        """Return recent monthly CPI/WPI inflation readings."""
        try:
            data = self._inflation_history[-months:] if self._inflation_history else []
            return {"months": months, "history": data, "_source": "rbi_dbie"}
        except Exception as exc:
            logger.error("rbi_dbie.inflation.error", error=str(exc))
            return {"error": str(exc), "error_code": "RBI_INFLATION_FAILED", "_source": "rbi_dbie"}

    async def load_from_db(self, pool: Any) -> None:
        """Refresh macro values and inflation history from PostgreSQL."""
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT repo_rate, cpi_inflation_pct, wpi_inflation_pct, "
                    "gdp_growth_pct, forex_reserves_usd_bn, usd_inr, "
                    "bank_rate, crr_pct, slr_pct, as_of "
                    "FROM macro_snapshot ORDER BY as_of DESC LIMIT 1"
                )
                if row:
                    self._macro.update(dict(row))
                    logger.info("rbi_dbie.macro.loaded_from_db")

                rows = await conn.fetch(
                    "SELECT month, cpi, wpi FROM inflation_history "
                    "ORDER BY month DESC LIMIT 36"
                )
                self._inflation_history = [dict(r) for r in reversed(rows)]
                logger.info("rbi_dbie.inflation_history.loaded", count=len(rows))
        except Exception:
            logger.warning("rbi_dbie.db_load_failed", exc_info=True)

    async def close(self) -> None:
        pass
