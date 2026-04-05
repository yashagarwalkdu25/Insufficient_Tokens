"""Morning brief tool — auto-generated daily summary for portfolio stocks.

Uses parallel data fetching for speed and generates a concise
actionable intelligence summary covering:
  - Portfolio P&L snapshot
  - Key price movers in holdings
  - Sentiment shifts detected
  - Macro indicators summary
  - Upcoming earnings for holdings
  - Active alert status
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import structlog

from ...server import mcp
from ...data_facade.facade import data_facade
from ...db import portfolio_repo, alerts_repo

logger = structlog.get_logger(__name__)


@mcp.tool()
async def generate_morning_brief(user_id: str = "demo") -> dict[str, Any]:
    """Generate a personalised morning intelligence brief for the user.

    Aggregates portfolio P&L, top movers, sentiment shifts, macro context,
    upcoming earnings, and active alerts into a single actionable summary.
    Fetches data in parallel for speed.

    Args:
        user_id: User identifier (auto-injected from JWT).
    """
    holdings = await portfolio_repo.get_holdings(user_id)
    if not holdings:
        return {
            "data": {
                "user_id": user_id,
                "greeting": "Good morning!",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "summary": "No holdings in your portfolio. Add stocks to get a personalised morning brief.",
                "portfolio": None,
                "top_movers": [],
                "sentiment_flags": [],
                "macro": None,
                "upcoming_earnings": [],
                "active_alerts": 0,
                "triggered_alerts": 0,
            },
            "source": "morning_brief",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    symbols = [h["symbol"] for h in holdings]

    # --- Parallel data fetch for all holdings ---
    price_tasks = [data_facade.get_price(s) for s in symbols]
    news_tasks = [data_facade.get_news(s, days=1) for s in symbols[:10]]  # cap at 10
    macro_task = data_facade.get_macro()
    alerts_task = alerts_repo.get_active_alerts(user_id)
    unread_task = alerts_repo.get_unread_count(user_id)

    all_results = await asyncio.gather(
        asyncio.gather(*price_tasks),
        asyncio.gather(*news_tasks),
        macro_task,
        alerts_task,
        unread_task,
        return_exceptions=True,
    )

    prices = all_results[0] if not isinstance(all_results[0], Exception) else [{}] * len(symbols)
    news_results = all_results[1] if not isinstance(all_results[1], Exception) else []
    macro = all_results[2] if not isinstance(all_results[2], Exception) else {}
    active_alerts = all_results[3] if not isinstance(all_results[3], Exception) else []
    unread_count = all_results[4] if not isinstance(all_results[4], Exception) else 0

    # --- Portfolio P&L Snapshot ---
    total_invested = 0.0
    total_current = 0.0
    movers: list[dict[str, Any]] = []

    for h, quote in zip(holdings, prices):
        ltp = quote.get("ltp") or h["avg_price"]
        change_pct = quote.get("change_pct") or 0
        invested = h["quantity"] * h["avg_price"]
        current = h["quantity"] * ltp
        total_invested += invested
        total_current += current
        movers.append({
            "symbol": h["symbol"],
            "ltp": ltp,
            "change_pct": round(change_pct, 2),
            "pnl": round(current - invested, 2),
            "pnl_pct": round((current - invested) / max(invested, 1) * 100, 2),
        })

    # Sort by absolute change % to find top movers
    movers.sort(key=lambda m: abs(m["change_pct"]), reverse=True)
    top_gainers = [m for m in movers if m["change_pct"] > 0][:3]
    top_losers = [m for m in movers if m["change_pct"] < 0][:3]

    total_pnl = total_current - total_invested
    total_pnl_pct = round((total_pnl / max(total_invested, 1)) * 100, 2)

    # --- Sentiment Snapshot (from 1-day news) ---
    sentiment_flags: list[dict[str, Any]] = []
    from ..news.tools import _keyword_sentiment, _get_source_credibility
    for i, s in enumerate(symbols[:len(news_results)]):
        articles = news_results[i].get("articles", news_results[i].get("data", [])) if isinstance(news_results[i], dict) else []
        if not articles:
            continue
        pos = sum(1 for a in articles if isinstance(a, dict) and _keyword_sentiment(a) > 0.15)
        neg = sum(1 for a in articles if isinstance(a, dict) and _keyword_sentiment(a) < -0.15)
        if neg > pos and neg >= 2:
            sentiment_flags.append({
                "symbol": s,
                "signal": "bearish",
                "negative_articles": neg,
                "total_articles": len(articles),
            })
        elif pos > neg and pos >= 2:
            sentiment_flags.append({
                "symbol": s,
                "signal": "bullish",
                "positive_articles": pos,
                "total_articles": len(articles),
            })

    # --- Macro Summary ---
    macro_summary = {
        "repo_rate": macro.get("repo_rate"),
        "cpi_latest": macro.get("cpi_inflation_pct") or macro.get("cpi_latest"),
        "usd_inr": macro.get("usd_inr"),
        "gdp_growth": macro.get("gdp_growth"),
    }

    # --- Upcoming Earnings ---
    try:
        cal = await data_facade.get_earnings_calendar(weeks=2)
        entries = cal.get("earnings", cal.get("data", []))
        upcoming_earnings = []
        symbols_set = set(s.upper() for s in symbols)
        for entry in entries:
            esym = (entry.get("symbol") or "").upper()
            if esym in symbols_set or any(esym.startswith(s) for s in symbols_set):
                upcoming_earnings.append({
                    "symbol": esym,
                    "date": entry.get("date") or entry.get("reportDate"),
                })
    except Exception:
        upcoming_earnings = []

    # --- Alerts summary ---
    triggered_alerts = [a for a in active_alerts if a.get("is_triggered")]
    pending_alerts = [a for a in active_alerts if not a.get("is_triggered")]

    # --- Build narrative summary ---
    lines = []
    lines.append(f"Portfolio: ₹{total_current:,.0f} ({total_pnl_pct:+.1f}% overall P&L)")
    if top_gainers:
        g = top_gainers[0]
        lines.append(f"Top gainer: {g['symbol']} {g['change_pct']:+.1f}% today")
    if top_losers:
        l = top_losers[0]
        lines.append(f"Top loser: {l['symbol']} {l['change_pct']:+.1f}% today")
    if sentiment_flags:
        bearish = [f["symbol"] for f in sentiment_flags if f["signal"] == "bearish"]
        if bearish:
            lines.append(f"Bearish sentiment detected: {', '.join(bearish)}")
    if upcoming_earnings:
        lines.append(f"Upcoming earnings: {', '.join(e['symbol'] for e in upcoming_earnings[:3])}")
    if unread_count > 0:
        lines.append(f"{unread_count} unread notification(s)")

    # Build top_movers list (combine gainers + losers)
    top_movers_combined = top_gainers + top_losers

    # Build sentiment_flags in the shape the frontend expects
    sentiment_flags_flat = [
        {
            "symbol": f["symbol"],
            "sentiment": f.get("positive_articles", 0) - f.get("negative_articles", 0),
            "direction": "positive" if f["signal"] == "bullish" else "negative",
        }
        for f in sentiment_flags
    ]

    # Build greeting
    hour = datetime.now(timezone.utc).hour + 5  # IST offset
    if hour < 12:
        greeting_text = "Good morning!"
    elif hour < 17:
        greeting_text = "Good afternoon!"
    else:
        greeting_text = "Good evening!"

    return {
        "data": {
            "user_id": user_id,
            "greeting": greeting_text,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": " | ".join(lines),
            "portfolio": {
                "total_invested": round(total_invested, 2),
                "current_value": round(total_current, 2),
                "total_pnl": round(total_pnl, 2),
                "total_pnl_pct": total_pnl_pct,
                "holdings_count": len(holdings),
            },
            "top_movers": top_movers_combined,
            "sentiment_flags": sentiment_flags_flat,
            "macro": macro_summary,
            "upcoming_earnings": upcoming_earnings,
            "active_alerts": len(pending_alerts),
            "triggered_alerts": len(triggered_alerts),
        },
        "source": "morning_brief",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "AI-generated summary. Not investment advice. Verify all data independently.",
    }
