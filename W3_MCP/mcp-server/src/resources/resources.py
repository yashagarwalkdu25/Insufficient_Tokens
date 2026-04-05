"""MCP Resources — URI-based contextual data for LLM clients."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ..server import mcp
from ..data_facade.facade import data_facade

from ..db import watchlist_repo
from ..db import research_cache_repo

from ..db import alerts_repo


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
    stocks = await watchlist_repo.get_watchlist(user_id)
    if not stocks:
        stocks = ["RELIANCE", "TCS", "HDFCBANK", "INFY"]
    return json.dumps({
        "user_id": user_id,
        "stocks": stocks,
        "count": len(stocks),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@mcp.resource("research://{ticker}/latest")
async def latest_research(ticker: str) -> str:
    """Most recent cached cross-source research brief for a ticker."""
    cache_key = f"research:{ticker.upper()}"
    cached = await research_cache_repo.get_cached(cache_key)
    if cached:
        return json.dumps(cached, default=str)
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
    holdings = await _get_holdings(user_id)
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
    holdings = await _get_holdings(user_id)
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
    holdings = await _get_holdings(user_id)
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


# ---------------------------------------------------------------------------
# Notification & Alert Resources
# ---------------------------------------------------------------------------

@mcp.resource("notifications://{user_id}/unread")
async def unread_notifications(user_id: str) -> str:
    """Unread notifications for a user — pollable subscription-style resource.

    Clients can poll this resource to detect new triggered alerts,
    price alerts, sentiment warnings, and earnings reminders.
    """
    notifs = await alerts_repo.get_notifications(user_id, unread_only=True, limit=20)
    unread_count = await alerts_repo.get_unread_count(user_id)
    for n in notifs:
        if isinstance(n.get("created_at"), datetime):
            n["created_at"] = n["created_at"].isoformat()
    return json.dumps({
        "user_id": user_id,
        "unread_count": unread_count,
        "notifications": notifs,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@mcp.resource("alerts://{user_id}/active")
async def active_alerts_resource(user_id: str) -> str:
    """Active alert rules for a user — price, risk, sentiment, earnings alerts."""
    alerts = await alerts_repo.get_active_alerts(user_id)
    for a in alerts:
        for key in ("triggered_at", "created_at"):
            if isinstance(a.get(key), datetime):
                a[key] = a[key].isoformat()
        if a.get("threshold") is not None:
            a["threshold"] = float(a["threshold"])
        if a.get("trigger_value") is not None:
            a["trigger_value"] = float(a["trigger_value"])
    return json.dumps({
        "user_id": user_id,
        "alerts": alerts,
        "active_count": len([a for a in alerts if not a.get("is_triggered")]),
        "triggered_count": len([a for a in alerts if a.get("is_triggered")]),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# ---------------------------------------------------------------------------
# Resource Subscriptions (MCP spec bonus)
# ---------------------------------------------------------------------------
# MCP resource subscriptions allow clients to register interest in resources
# and receive change notifications. We track subscriptions in-memory and
# provide a tool for clients to subscribe/unsubscribe.

_subscriptions: dict[str, set[str]] = {}  # user_id -> set of resource URIs


@mcp.tool()
async def subscribe_resource(
    resource_uri: str,
    user_id: str = "demo",
) -> dict[str, Any]:
    """Subscribe to change notifications for an MCP resource.

    When subscribed, the resource data will be included in periodic
    polling responses and morning briefs.

    Subscribable resources:
      - portfolio://{user_id}/alerts
      - portfolio://{user_id}/risk_score
      - notifications://{user_id}/unread
      - market://overview
      - macro://snapshot

    Args:
        resource_uri: The MCP resource URI to subscribe to.
        user_id: User identifier (auto-injected from JWT).
    """
    user_subs = _subscriptions.setdefault(user_id, set())
    user_subs.add(resource_uri)
    return {
        "data": {
            "subscribed": resource_uri,
            "total_subscriptions": len(user_subs),
            "all_subscriptions": sorted(user_subs),
        },
        "source": "local",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@mcp.tool()
async def unsubscribe_resource(
    resource_uri: str,
    user_id: str = "demo",
) -> dict[str, Any]:
    """Unsubscribe from change notifications for an MCP resource.

    Args:
        resource_uri: The MCP resource URI to unsubscribe from.
        user_id: User identifier (auto-injected from JWT).
    """
    user_subs = _subscriptions.get(user_id, set())
    user_subs.discard(resource_uri)
    return {
        "data": {
            "unsubscribed": resource_uri,
            "total_subscriptions": len(user_subs),
            "all_subscriptions": sorted(user_subs),
        },
        "source": "local",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@mcp.tool()
async def get_subscribed_updates(user_id: str = "demo") -> dict[str, Any]:
    """Fetch latest data for all subscribed resources in a single call.

    Returns a batch response with the current value of each resource
    the user has subscribed to. Useful for periodic polling.

    Args:
        user_id: User identifier (auto-injected from JWT).
    """
    user_subs = _subscriptions.get(user_id, set())
    if not user_subs:
        return {
            "data": {
                "user_id": user_id,
                "subscriptions": [],
                "updates": {},
                "hint": "Use subscribe_resource to watch resources.",
            },
            "source": "local",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    updates: dict[str, Any] = {}
    for uri in sorted(user_subs):
        try:
            result = await mcp.read_resource(uri)
            if hasattr(result, "contents") and result.contents:
                content = result.contents[0]
                if hasattr(content, "text"):
                    updates[uri] = json.loads(content.text)
                else:
                    updates[uri] = str(content)
            else:
                updates[uri] = str(result)
        except Exception as exc:
            updates[uri] = {"error": str(exc)}

    return {
        "data": {
            "user_id": user_id,
            "subscriptions": sorted(user_subs),
            "updates": updates,
        },
        "source": "local",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
