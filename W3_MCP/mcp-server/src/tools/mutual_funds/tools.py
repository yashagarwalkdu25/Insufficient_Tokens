"""Mutual fund tools — search, NAV retrieval, and fund comparison."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ...server import mcp
from ...data_facade.facade import data_facade


@mcp.tool()
async def search_mutual_funds(query: str) -> dict[str, Any]:
    """Search Indian mutual fund schemes by name, AMC, or category.

    Returns a list of matching schemes with scheme codes, fund names, AMC,
    category, and latest NAV.  Uses the AMFI MFApi data source.

    Args:
        query: Free-text search query (e.g. "axis bluechip", "large cap",
               "SBI equity").

    Returns:
        dict with keys: data (list of matching funds), source, cache_status,
        timestamp, disclaimer.
    """
    result = await data_facade.get_mf_search(query)
    return {
        "data": {
            "query": query,
            "results": result.get("schemes", result.get("results", [])),
            "total_matches": result.get("total", 0),
        },
        "source": result.get("_source", "unknown"),
        "cache_status": result.get("_cache", "miss"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "For informational purposes only. Not investment advice.",
    }


@mcp.tool()
async def get_fund_nav(scheme_code: str) -> dict[str, Any]:
    """Get the latest NAV and historical NAV data for an Indian mutual fund.

    Returns the current net asset value, fund name, and a time-series of
    recent NAVs for charting and analysis.

    Args:
        scheme_code: AMFI scheme code (e.g. "119551" for Axis Bluechip Fund).

    Returns:
        dict with keys: data, source, cache_status, timestamp, disclaimer.
    """
    result = await data_facade.get_mf_nav(scheme_code)
    return {
        "data": {
            "scheme_code": scheme_code,
            "fund_name": result.get("fund_name", result.get("scheme_name")),
            "nav": result.get("nav"),
            "nav_date": result.get("date", result.get("nav_date")),
            "nav_history": result.get("nav_history", []),
        },
        "source": result.get("_source", "unknown"),
        "cache_status": result.get("_cache", "miss"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "For informational purposes only. Not investment advice.",
    }


@mcp.tool()
async def compare_funds(scheme_codes: str) -> dict[str, Any]:
    """Side-by-side comparison of multiple Indian mutual fund schemes.

    Fetches NAV and metadata for each scheme and returns a comparison
    including fund name, latest NAV, 1Y/3Y/5Y returns where available.

    Args:
        scheme_codes: Comma-separated AMFI scheme codes (e.g. "119551,120503").

    Returns:
        dict with keys: data, source, cache_status, timestamp, disclaimer.
    """
    code_list = [c.strip() for c in scheme_codes.split(",")]
    comparison: dict[str, Any] = {}
    sources: list[str] = []

    for code in code_list:
        result = await data_facade.get_mf_nav(code)
        sources.append(result.get("_source", "unknown"))
        comparison[code] = {
            "fund_name": result.get("fund_name", result.get("scheme_name")),
            "nav": result.get("nav"),
            "nav_date": result.get("date", result.get("nav_date")),
            "returns_1y": result.get("returns_1y"),
            "returns_3y": result.get("returns_3y"),
            "returns_5y": result.get("returns_5y"),
            "expense_ratio": result.get("expense_ratio"),
            "category": result.get("category"),
        }

    return {
        "data": {
            "scheme_codes": code_list,
            "comparison": comparison,
        },
        "source": ", ".join(set(sources)),
        "cache_status": "mixed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "For informational purposes only. Not investment advice.",
    }
