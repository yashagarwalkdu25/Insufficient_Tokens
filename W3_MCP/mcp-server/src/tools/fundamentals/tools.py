"""Fundamental analysis tools — financials, ratios, shareholding, quarterlies, and peer comparison."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ...server import mcp
from ...data_facade.facade import data_facade


@mcp.tool()
async def get_financial_statements(
    symbol: str,
    statement_type: str = "income",
    period: str = "annual",
) -> dict[str, Any]:
    """Retrieve financial statements for an Indian listed company.

    Returns revenue, operating profit, net profit, EPS, total assets,
    liabilities, equity, and operating cash flow for the requested period.

    Args:
        symbol: NSE/BSE ticker symbol (e.g. "RELIANCE").
        statement_type: One of "income", "balance_sheet", or "cash_flow".
        period: "annual" or "quarterly".

    Returns:
        dict with keys: data, source, cache_status, timestamp, disclaimer.
    """
    result = await data_facade.get_fundamentals(symbol)
    statements = result.get("statements", result)
    return {
        "data": {
            "symbol": symbol,
            "statement_type": statement_type,
            "period": period,
            "statements": statements if isinstance(statements, list) else [statements],
        },
        "source": result.get("_source", "unknown"),
        "cache_status": result.get("_cache", "miss"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "For informational purposes only. Not investment advice.",
    }


@mcp.tool()
async def get_key_ratios(symbol: str) -> dict[str, Any]:
    """Get key valuation and profitability ratios for an Indian equity.

    Returns P/E ratio, P/B ratio, ROE, ROCE, debt-to-equity, current ratio,
    dividend yield, EV/EBITDA, price-to-sales, and sector-average P/E for
    benchmarking.

    Args:
        symbol: NSE/BSE ticker symbol (e.g. "TCS").

    Returns:
        dict with keys: data, source, cache_status, timestamp, disclaimer.
    """
    result = await data_facade.get_fundamentals(symbol)

    eps = result.get("eps")
    pe_ratio = result.get("pe_ratio")
    roe = result.get("roe")
    dividend_yield = result.get("dividend_yield")

    # Explain missing ratios for transparency
    notes: list[str] = []
    if eps is not None and eps < 0 and pe_ratio is None:
        notes.append("P/E ratio is not applicable — company has negative earnings (EPS < 0).")
    if roe is None and eps is not None and eps < 0:
        notes.append("ROE is not available — may indicate negative equity or loss-making status.")
    if dividend_yield is None:
        notes.append("No dividend yield — the company may not pay dividends.")

    data: dict[str, Any] = {
        "symbol": symbol,
        "pe_ratio": pe_ratio,
        "pb_ratio": result.get("pb_ratio"),
        "roe": roe,
        "roce": result.get("roce"),
        "debt_to_equity": result.get("debt_to_equity"),
        "current_ratio": result.get("current_ratio"),
        "dividend_yield": dividend_yield,
        "ev_to_ebitda": result.get("ev_to_ebitda"),
        "price_to_sales": result.get("price_to_sales"),
        "eps": eps,
        "sector": result.get("sector"),
        "industry": result.get("industry"),
        "sector_avg_pe": result.get("sector_avg_pe"),
    }
    if notes:
        data["notes"] = notes

    return {
        "data": data,
        "source": result.get("_source", "unknown"),
        "cache_status": result.get("_cache", "miss"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "For informational purposes only. Not investment advice.",
    }


@mcp.tool()
async def get_shareholding_pattern(
    symbol: str,
    quarters: int = 4,
) -> dict[str, Any]:
    """Get the quarterly shareholding pattern for an Indian listed company.

    Returns promoter, FII, DII, retail, and other institutional ownership
    percentages for the last N quarters, useful for tracking institutional
    accumulation or distribution.

    Args:
        symbol: NSE/BSE ticker symbol (e.g. "HDFCBANK").
        quarters: Number of recent quarters to include (default 4, max 12).

    Returns:
        dict with keys: data, source, cache_status, timestamp, disclaimer.
    """
    result = await data_facade.get_shareholding(symbol, quarters)
    entries = result.get("entries", [])

    has_valid_data = any(
        e.get("promoter") is not None or e.get("fii") is not None
        for e in entries
        if isinstance(e, dict)
    )

    data: dict[str, Any] = {
        "symbol": symbol,
        "quarters_requested": quarters,
        "entries": entries[:quarters],
    }
    if not has_valid_data:
        data["data_note"] = (
            "Shareholding data is unavailable from automated sources for this stock. "
            "Check BSE/NSE websites for official SEBI-mandated disclosures."
        )

    return {
        "data": data,
        "source": result.get("_source", "unknown"),
        "cache_status": result.get("_cache", "miss"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "For informational purposes only. Not investment advice.",
    }


@mcp.tool()
async def get_quarterly_results(symbol: str) -> dict[str, Any]:
    """Get the latest quarterly financial results for an Indian company.

    Returns revenue, net profit, EPS, operating margin, and year-on-year /
    quarter-on-quarter growth rates for the most recent quarter.

    Args:
        symbol: NSE/BSE ticker symbol (e.g. "INFY").

    Returns:
        dict with keys: data, source, cache_status, timestamp, disclaimer.
    """
    result = await data_facade.get_filings(symbol, filing_type="results")
    return {
        "data": {
            "symbol": symbol,
            "quarter": result.get("quarter"),
            "revenue": result.get("revenue"),
            "net_profit": result.get("net_profit"),
            "eps": result.get("eps"),
            "yoy_revenue_growth": result.get("yoy_revenue_growth"),
            "qoq_revenue_growth": result.get("qoq_revenue_growth"),
            "yoy_profit_growth": result.get("yoy_profit_growth"),
            "margin_pct": result.get("margin_pct"),
        },
        "source": result.get("_source", "unknown"),
        "cache_status": result.get("_cache", "miss"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "For informational purposes only. Not investment advice.",
    }


@mcp.tool()
async def compare_companies(symbols: str) -> dict[str, Any]:
    """Side-by-side comparison of key metrics for multiple Indian equities.

    Fetches fundamentals for each symbol and returns a comparison table with
    P/E, P/B, ROE, ROCE, debt-to-equity, revenue growth, and margin data.
    Requires Analyst tier access.

    Args:
        symbols: Comma-separated NSE/BSE ticker symbols (e.g. "TCS,INFY,WIPRO").

    Returns:
        dict with keys: data, source, cache_status, timestamp, disclaimer.
    """
    symbol_list = [s.strip().upper() for s in symbols.split(",")]
    comparison: dict[str, Any] = {}
    sources: list[str] = []

    for sym in symbol_list:
        result = await data_facade.get_fundamentals(sym)
        sources.append(result.get("_source", "unknown"))
        comparison[sym] = {
            "pe_ratio": result.get("pe_ratio"),
            "pb_ratio": result.get("pb_ratio"),
            "roe": result.get("roe"),
            "roce": result.get("roce"),
            "debt_to_equity": result.get("debt_to_equity"),
            "revenue": result.get("revenue"),
            "net_profit": result.get("net_profit"),
            "margin_pct": result.get("margin_pct"),
        }

    return {
        "data": {
            "symbols": symbol_list,
            "comparison": comparison,
        },
        "source": ", ".join(set(sources)),
        "cache_status": "mixed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "For informational purposes only. Not investment advice.",
    }
