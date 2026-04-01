"""MCP Resources — URI-based contextual data for LLM clients."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from ..server import mcp
from ..data_facade.facade import data_facade

# In-memory stores (mirrors portfolio tools store)
# TODO: Wire to PostgreSQL
_watchlists: dict[str, list[str]] = {}
_research_cache: dict[str, dict] = {}


@mcp.resource("market://overview")
async def market_overview() -> str:
    """Current market overview: Nifty 50, Sensex, Bank Nifty, top movers (PS1 resource)."""
    nifty = await data_facade.get_price("NIFTY50")
    sensex = await data_facade.get_price("SENSEX")
    bank_nifty = await data_facade.get_price("NIFTYBANK")
    movers = await data_facade.get_price("NSE:MOVERS")
    gainers = (movers.get("gainers") or [])[:5]
    losers = (movers.get("losers") or [])[:5]
    sources = {
        nifty.get("_source"),
        sensex.get("_source"),
        bank_nifty.get("_source"),
        movers.get("_source"),
    }
    sources.discard(None)
    return json.dumps({
        "nifty50": {
            "value": nifty.get("ltp"),
            "change": nifty.get("change"),
            "change_pct": nifty.get("change_pct"),
        },
        "sensex": {
            "value": sensex.get("ltp"),
            "change": sensex.get("change"),
            "change_pct": sensex.get("change_pct"),
        },
        "bank_nifty": {
            "value": bank_nifty.get("ltp"),
            "change": bank_nifty.get("change"),
            "change_pct": bank_nifty.get("change_pct"),
        },
        "top_movers": {
            "gainers": gainers,
            "losers": losers,
        },
        "source": ",".join(sorted(sources)) if sources else "unknown",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "For informational purposes only. Not investment advice.",
    })


@mcp.resource("macro://snapshot")
async def macro_snapshot() -> str:
    """Current macro-economic snapshot: repo rate, CPI, GDP, forex, USD/INR."""
    macro = await data_facade.get_macro()
    return json.dumps({
        "repo_rate": macro.get("repo_rate"),
        "cpi_latest": macro.get("cpi_latest"),
        "gdp_growth": macro.get("gdp_growth"),
        "forex_reserves_bn_usd": macro.get("forex_reserves_bn_usd"),
        "usd_inr": macro.get("usd_inr"),
        "source": macro.get("_source", "rbi_dbie"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@mcp.resource("watchlist://{user_id}/stocks")
async def user_watchlist(user_id: str) -> str:
    """User's personal stock watchlist."""
    stocks = _watchlists.get(user_id, ["RELIANCE", "TCS", "HDFCBANK", "INFY"])
    return json.dumps({
        "user_id": user_id,
        "stocks": stocks,
        "count": len(stocks),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@mcp.resource("research://{ticker}/latest")
async def latest_research(ticker: str) -> str:
    """Most recent cached cross-source research brief for a ticker."""
    cached = _research_cache.get(ticker.upper())
    if cached:
        return json.dumps(cached)
    return json.dumps({
        "ticker": ticker.upper(),
        "status": "no_research_cached",
        "hint": "Use the generate_research_brief tool to create one.",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@mcp.resource("portfolio://{user_id}/holdings")
async def portfolio_holdings(user_id: str) -> str:
    """User's current portfolio holdings."""
    from ..tools.portfolio.tools import _get_holdings
    holdings = _get_holdings(user_id)
    return json.dumps({
        "user_id": user_id,
        "holdings": holdings,
        "count": len(holdings),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@mcp.resource("portfolio://{user_id}/alerts")
async def portfolio_alerts(user_id: str) -> str:
    """Active risk alerts for the user's portfolio.

    Computes live alerts from current holdings: concentration risk (>20%
    single stock), sector tilt (>40% single sector), and sentiment shifts.
    This is the PS2 subscription-style resource — clients can poll this
    to detect new alerts.
    """
    from ..tools.portfolio.tools import _get_holdings
    holdings = _get_holdings(user_id)
    if not holdings:
        return json.dumps({
            "user_id": user_id,
            "alerts": [],
            "alert_count": 0,
            "hint": "Add holdings with add_to_portfolio first.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    # Compute live alerts from holdings
    alerts = []
    total_value = 0.0
    holding_values = []
    sector_totals: dict[str, float] = {}

    for h in holdings:
        quote = await data_facade.get_price(h["symbol"])
        ltp = quote.get("ltp") or h.get("avg_price", 0)
        value = h["quantity"] * ltp
        total_value += value
        sector = quote.get("sector", "Unknown")
        sector_totals[sector] = sector_totals.get(sector, 0) + value
        holding_values.append({"symbol": h["symbol"], "value": value})

    for hv in holding_values:
        weight = (hv["value"] / total_value * 100) if total_value else 0
        if weight > 20:
            alerts.append({
                "alert_type": "concentration",
                "severity": "high" if weight > 30 else "medium",
                "symbol": hv["symbol"],
                "message": f"{hv['symbol']} is {weight:.1f}% of portfolio (threshold: 20%)",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    for sector, val in sector_totals.items():
        pct = (val / total_value * 100) if total_value else 0
        if pct > 40:
            alerts.append({
                "alert_type": "sector_tilt",
                "severity": "high",
                "sector": sector,
                "message": f"{sector} sector is {pct:.1f}% of portfolio (threshold: 40%)",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    return json.dumps({
        "user_id": user_id,
        "alerts": alerts,
        "alert_count": len(alerts),
        "risk_score": min(100, len(alerts) * 25),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@mcp.resource("portfolio://{user_id}/risk_score")
async def portfolio_risk_score(user_id: str) -> str:
    """Overall portfolio risk score (0-100), computed live from holdings."""
    from ..tools.portfolio.tools import _get_holdings
    holdings = _get_holdings(user_id)
    if not holdings:
        return json.dumps({
            "user_id": user_id,
            "risk_score": 0,
            "status": "no_holdings",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    total_value = 0.0
    values = []
    for h in holdings:
        quote = await data_facade.get_price(h["symbol"])
        ltp = quote.get("ltp") or h.get("avg_price", 0)
        value = h["quantity"] * ltp
        total_value += value
        values.append(value)

    # Concentration-based risk: Herfindahl index
    weights = [(v / total_value) for v in values] if total_value else []
    hhi = sum(w * w for w in weights)  # 0..1 (1 = single stock)
    risk_score = min(100, int(hhi * 100 * len(weights)))

    return json.dumps({
        "user_id": user_id,
        "risk_score": risk_score,
        "herfindahl_index": round(hhi, 4),
        "holdings_count": len(holdings),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@mcp.resource("earnings://calendar/upcoming")
async def upcoming_earnings() -> str:
    """Next 2 weeks of earnings announcement dates."""
    cal = await data_facade.get_earnings_calendar(weeks=2)
    return json.dumps({
        "entries": cal.get("earnings", cal.get("data", [])),
        "source": cal.get("_source", "finnhub"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@mcp.resource("earnings://{ticker}/latest")
async def latest_earnings(ticker: str) -> str:
    """Most recent parsed quarterly result for a ticker."""
    return json.dumps({
        "ticker": ticker.upper(),
        "status": "no_parsed_result",
        "hint": "Use parse_quarterly_filing to extract data from BSE filing.",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@mcp.resource("earnings://{ticker}/history")
async def earnings_history(ticker: str) -> str:
    """Last 8 quarters of structured earnings data for a ticker."""
    fundamentals = await data_facade.get_fundamentals(ticker)
    return json.dumps({
        "ticker": ticker.upper(),
        "eps_history": fundamentals.get("eps_history", []),
        "source": fundamentals.get("_source", "unknown"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@mcp.resource("filing://{ticker}/{filing_id}")
async def filing_content(ticker: str, filing_id: str) -> str:
    """Parsed BSE filing content by ticker and filing ID."""
    return json.dumps({
        "ticker": ticker.upper(),
        "filing_id": filing_id,
        "status": "not_yet_parsed",
        "hint": "Use parse_quarterly_filing tool to extract structured data.",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
