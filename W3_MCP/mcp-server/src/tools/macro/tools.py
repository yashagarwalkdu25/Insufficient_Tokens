"""Macro-economic tools — RBI rates, inflation data."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ...server import mcp
from ...data_facade.facade import data_facade


@mcp.tool()
async def get_rbi_rates() -> dict[str, Any]:
    """Get current RBI monetary policy rates.

    Returns the repo rate, reverse repo rate, CRR, SLR, and the date
    they were last updated. Source: RBI DBIE (pre-fetched).
    """
    result = await data_facade.get_macro()
    return {
        "data": {
            "repo_rate": result.get("repo_rate"),
            "reverse_repo_rate": result.get("reverse_repo_rate"),
            "crr": result.get("crr"),
            "slr": result.get("slr"),
            "as_of_date": result.get("as_of_date"),
        },
        "source": result.get("_source", "rbi_dbie"),
        "cache_status": result.get("_cache", "miss"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "Macro data sourced from RBI DBIE. Verify on data.rbi.org.in.",
    }


@mcp.tool()
async def get_inflation_data(months: int = 12) -> dict[str, Any]:
    """Get Indian CPI and WPI inflation time series.

    Returns monthly inflation data for the requested number of months.
    Source: RBI DBIE (pre-fetched).

    Args:
        months: Number of months of history to return (default 12).
    """
    result = await data_facade.get_macro()
    return {
        "data": {
            "months_requested": months,
            "cpi_latest": result.get("cpi_latest"),
            "wpi_latest": result.get("wpi_latest"),
            "gdp_growth": result.get("gdp_growth"),
            "forex_reserves_bn_usd": result.get("forex_reserves_bn_usd"),
            "usd_inr": result.get("usd_inr"),
        },
        "source": result.get("_source", "rbi_dbie"),
        "cache_status": result.get("_cache", "miss"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "Macro data sourced from RBI DBIE. Verify on data.rbi.org.in.",
    }
