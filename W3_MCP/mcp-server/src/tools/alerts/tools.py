"""Alert & notification tools — create price alerts, manage notifications, check alerts."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ...server import mcp
from ...data_facade.facade import data_facade
from ...db import alerts_repo, portfolio_repo

import structlog

logger = structlog.get_logger(__name__)


@mcp.tool()
async def create_price_alert(
    symbol: str,
    threshold: float,
    direction: str = "below",
    user_id: str = "demo",
) -> dict[str, Any]:
    """Create a price alert for a stock.

    Triggers a notification when the stock price crosses the specified
    threshold in the given direction.

    Args:
        symbol: NSE/BSE ticker symbol (e.g. "RELIANCE").
        threshold: Target price level (e.g. 2400.0).
        direction: "below" to alert when price drops below threshold,
                   "above" to alert when price rises above threshold.
        user_id: User identifier (auto-injected from JWT).
    """
    symbol = symbol.strip().upper()
    direction = direction.strip().lower()
    if direction not in ("below", "above"):
        return {"error": "direction must be 'below' or 'above'", "error_code": "INVALID_DIRECTION"}

    # Verify symbol
    quote = await data_facade.get_price(symbol)
    ltp = quote.get("ltp") if isinstance(quote, dict) else None
    if ltp is None or ltp == 0:
        return {"error": f"Symbol '{symbol}' not found.", "error_code": "SYMBOL_NOT_FOUND"}

    condition = f"price_{direction}_{threshold}"
    alert_id = await alerts_repo.create_alert(
        user_id=user_id,
        alert_type="price",
        symbol=symbol,
        condition=condition,
        threshold=threshold,
        direction=direction,
    )
    return {
        "data": {
            "alert_id": alert_id,
            "symbol": symbol,
            "alert_type": "price",
            "threshold": threshold,
            "direction": direction,
            "current_price": ltp,
            "status": "active",
        },
        "source": "local",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@mcp.tool()
async def create_portfolio_risk_alert(
    risk_type: str = "concentration",
    threshold: float = 20.0,
    user_id: str = "demo",
) -> dict[str, Any]:
    """Create a portfolio risk alert.

    Monitors the portfolio for risk conditions and triggers a
    notification when thresholds are breached.

    Args:
        risk_type: Type of risk — "concentration" (single stock >threshold%),
                   "sector_tilt" (single sector >threshold%), or
                   "drawdown" (portfolio value drops >threshold%).
        threshold: Percentage threshold (default 20.0).
        user_id: User identifier (auto-injected from JWT).
    """
    valid_types = {"concentration", "sector_tilt", "drawdown"}
    if risk_type not in valid_types:
        return {"error": f"risk_type must be one of {valid_types}", "error_code": "INVALID_RISK_TYPE"}

    condition = f"{risk_type}_exceeds_{threshold}pct"
    alert_id = await alerts_repo.create_alert(
        user_id=user_id,
        alert_type="portfolio_risk",
        symbol=None,
        condition=condition,
        threshold=threshold,
        direction="above",
    )
    return {
        "data": {
            "alert_id": alert_id,
            "alert_type": "portfolio_risk",
            "risk_type": risk_type,
            "threshold": threshold,
            "status": "active",
        },
        "source": "local",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@mcp.tool()
async def create_sentiment_alert(
    symbol: str,
    threshold: float = -0.3,
    user_id: str = "demo",
) -> dict[str, Any]:
    """Create a sentiment shift alert for a stock.

    Triggers when news sentiment for the stock drops below the
    specified threshold (bearish) or rises above it (bullish).

    Args:
        symbol: NSE/BSE ticker symbol.
        threshold: Sentiment score threshold (-1.0 to 1.0). Negative = bearish alert.
        user_id: User identifier (auto-injected from JWT).
    """
    symbol = symbol.strip().upper()
    direction = "below" if threshold < 0 else "above"
    condition = f"sentiment_{direction}_{threshold}"
    alert_id = await alerts_repo.create_alert(
        user_id=user_id,
        alert_type="sentiment",
        symbol=symbol,
        condition=condition,
        threshold=threshold,
        direction=direction,
    )
    return {
        "data": {
            "alert_id": alert_id,
            "symbol": symbol,
            "alert_type": "sentiment",
            "threshold": threshold,
            "direction": direction,
            "status": "active",
        },
        "source": "local",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@mcp.tool()
async def create_earnings_reminder(
    symbol: str,
    days_before: int = 3,
    user_id: str = "demo",
) -> dict[str, Any]:
    """Create an earnings date reminder for a stock.

    Triggers a notification N days before the stock's next earnings
    announcement date.

    Args:
        symbol: NSE/BSE ticker symbol.
        days_before: How many days before earnings to trigger (default 3).
        user_id: User identifier (auto-injected from JWT).
    """
    symbol = symbol.strip().upper()
    condition = f"earnings_reminder_{days_before}d"
    alert_id = await alerts_repo.create_alert(
        user_id=user_id,
        alert_type="earnings_reminder",
        symbol=symbol,
        condition=condition,
        threshold=float(days_before),
        direction="below",
    )
    return {
        "data": {
            "alert_id": alert_id,
            "symbol": symbol,
            "alert_type": "earnings_reminder",
            "days_before": days_before,
            "status": "active",
        },
        "source": "local",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@mcp.tool()
async def get_my_alerts(user_id: str = "demo") -> dict[str, Any]:
    """Get all active alerts for the current user.

    Returns price alerts, portfolio risk alerts, sentiment alerts,
    and earnings reminders with their current status.

    Args:
        user_id: User identifier (auto-injected from JWT).
    """
    alerts = await alerts_repo.get_active_alerts(user_id)
    # Serialise datetime objects
    for a in alerts:
        for key in ("triggered_at", "created_at"):
            if isinstance(a.get(key), datetime):
                a[key] = a[key].isoformat()
        if a.get("threshold") is not None:
            a["threshold"] = float(a["threshold"])
        if a.get("trigger_value") is not None:
            a["trigger_value"] = float(a["trigger_value"])

    return {
        "data": {
            "user_id": user_id,
            "alerts": alerts,
            "total_active": len([a for a in alerts if not a.get("is_triggered")]),
            "total_triggered": len([a for a in alerts if a.get("is_triggered")]),
        },
        "source": "local",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@mcp.tool()
async def delete_alert(alert_id: int, user_id: str = "demo") -> dict[str, Any]:
    """Delete (deactivate) an alert by its ID.

    Args:
        alert_id: The numeric ID of the alert to delete.
        user_id: User identifier (auto-injected from JWT).
    """
    success = await alerts_repo.delete_alert(user_id, alert_id)
    return {
        "data": {"alert_id": alert_id, "deleted": success},
        "source": "local",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@mcp.tool()
async def get_notifications(
    unread_only: bool = False,
    limit: int = 50,
    user_id: str = "demo",
) -> dict[str, Any]:
    """Get recent notifications for the current user.

    Returns triggered alerts and system notifications sorted by recency.

    Args:
        unread_only: If true, only return unread notifications.
        limit: Maximum number of notifications to return (default 50).
        user_id: User identifier (auto-injected from JWT).
    """
    notifs = await alerts_repo.get_notifications(user_id, unread_only=unread_only, limit=limit)
    unread_count = await alerts_repo.get_unread_count(user_id)
    # Serialise datetime objects
    for n in notifs:
        if isinstance(n.get("created_at"), datetime):
            n["created_at"] = n["created_at"].isoformat()

    return {
        "data": {
            "user_id": user_id,
            "notifications": notifs,
            "unread_count": unread_count,
            "total_returned": len(notifs),
        },
        "source": "local",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@mcp.tool()
async def mark_notifications_read(
    notification_ids: list[int] | None = None,
    user_id: str = "demo",
) -> dict[str, Any]:
    """Mark notifications as read.

    If notification_ids is provided, only those are marked. Otherwise
    all unread notifications for the user are marked as read.

    Args:
        notification_ids: List of notification IDs to mark (optional — marks all if omitted).
        user_id: User identifier (auto-injected from JWT).
    """
    count = await alerts_repo.mark_notifications_read(user_id, notification_ids)
    return {
        "data": {"marked_read": count},
        "source": "local",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@mcp.tool()
async def check_and_trigger_alerts(user_id: str = "demo") -> dict[str, Any]:
    """Evaluate all active alerts and trigger any that match.

    Checks price alerts against current prices, portfolio risk alerts
    against current portfolio state, and sentiment alerts against
    recent news. Generates notifications for triggered alerts.

    Args:
        user_id: User identifier (auto-injected from JWT).
    """
    alerts = await alerts_repo.get_active_alerts(user_id)
    triggered = []
    checked = 0

    for alert in alerts:
        if alert.get("is_triggered"):
            continue
        checked += 1
        alert_type = alert["alert_type"]
        alert_id = alert["id"]

        try:
            if alert_type == "price":
                result = await _check_price_alert(alert)
            elif alert_type == "portfolio_risk":
                result = await _check_portfolio_risk_alert(alert, user_id)
            elif alert_type == "sentiment":
                result = await _check_sentiment_alert(alert)
            elif alert_type == "earnings_reminder":
                result = await _check_earnings_reminder(alert)
            else:
                result = None

            if result:
                await alerts_repo.trigger_alert(alert_id, result.get("value"), result["message"])
                await alerts_repo.create_notification(
                    user_id=user_id,
                    title=result["title"],
                    message=result["message"],
                    severity=result.get("severity", "warning"),
                    alert_id=alert_id,
                )
                triggered.append({
                    "alert_id": alert_id,
                    "alert_type": alert_type,
                    "symbol": alert.get("symbol"),
                    "message": result["message"],
                })
        except Exception as exc:
            logger.error("alert_check_failed", alert_id=alert_id, error=str(exc))

    return {
        "data": {
            "user_id": user_id,
            "alerts_checked": checked,
            "alerts_triggered": len(triggered),
            "triggered": triggered,
        },
        "source": "local",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Internal alert evaluation helpers
# ---------------------------------------------------------------------------

async def _check_price_alert(alert: dict[str, Any]) -> dict[str, Any] | None:
    """Check a price alert against current market data."""
    symbol = alert.get("symbol")
    threshold = float(alert.get("threshold", 0))
    direction = alert.get("direction", "below")
    if not symbol:
        return None

    quote = await data_facade.get_price(symbol)
    ltp = quote.get("ltp")
    if ltp is None:
        return None

    if direction == "below" and ltp <= threshold:
        return {
            "title": f"Price Alert: {symbol} ≤ ₹{threshold:,.2f}",
            "message": f"{symbol} is now at ₹{ltp:,.2f}, below your threshold of ₹{threshold:,.2f}",
            "severity": "warning",
            "value": ltp,
        }
    elif direction == "above" and ltp >= threshold:
        return {
            "title": f"Price Alert: {symbol} ≥ ₹{threshold:,.2f}",
            "message": f"{symbol} is now at ₹{ltp:,.2f}, above your threshold of ₹{threshold:,.2f}",
            "severity": "info",
            "value": ltp,
        }
    return None


async def _check_portfolio_risk_alert(alert: dict[str, Any], user_id: str) -> dict[str, Any] | None:
    """Check portfolio risk against thresholds."""
    threshold = float(alert.get("threshold", 20))
    condition = alert.get("condition", "")

    holdings = await portfolio_repo.get_holdings(user_id)
    if not holdings:
        return None

    # Get current values
    total_value = 0.0
    holding_values: list[dict[str, Any]] = []
    sector_totals: dict[str, float] = {}

    for h in holdings:
        quote = await data_facade.get_price(h["symbol"])
        ltp = quote.get("ltp") or h.get("avg_price", 0)
        value = h["quantity"] * ltp
        total_value += value
        sector = quote.get("sector", "Unknown")
        sector_totals[sector] = sector_totals.get(sector, 0) + value
        holding_values.append({"symbol": h["symbol"], "value": value})

    if "concentration" in condition:
        for hv in holding_values:
            weight = (hv["value"] / total_value * 100) if total_value else 0
            if weight > threshold:
                return {
                    "title": f"Concentration Risk: {hv['symbol']} at {weight:.1f}%",
                    "message": f"{hv['symbol']} is {weight:.1f}% of your portfolio, exceeding your {threshold}% threshold",
                    "severity": "high",
                    "value": weight,
                }
    elif "sector_tilt" in condition:
        for sector, val in sector_totals.items():
            pct = (val / total_value * 100) if total_value else 0
            if pct > threshold:
                return {
                    "title": f"Sector Tilt Alert: {sector} at {pct:.1f}%",
                    "message": f"{sector} sector is {pct:.1f}% of your portfolio, exceeding your {threshold}% threshold",
                    "severity": "high",
                    "value": pct,
                }
    elif "drawdown" in condition:
        # Compare current value vs invested value
        total_invested = sum(h["quantity"] * h["avg_price"] for h in holdings)
        if total_invested > 0:
            drawdown_pct = ((total_invested - total_value) / total_invested) * 100
            if drawdown_pct > threshold:
                return {
                    "title": f"Drawdown Alert: Portfolio down {drawdown_pct:.1f}%",
                    "message": f"Your portfolio has declined {drawdown_pct:.1f}% from cost basis, exceeding your {threshold}% threshold",
                    "severity": "high",
                    "value": drawdown_pct,
                }
    return None


async def _check_sentiment_alert(alert: dict[str, Any]) -> dict[str, Any] | None:
    """Check sentiment for a stock against threshold."""
    from ..news.tools import _keyword_sentiment

    symbol = alert.get("symbol")
    threshold = float(alert.get("threshold", -0.3))
    direction = alert.get("direction", "below")
    if not symbol:
        return None

    news = await data_facade.get_news(symbol, days=7)
    articles = news.get("articles", news.get("data", []))
    count = max(len(articles), 1)

    pos = neg = 0
    for a in articles:
        if not isinstance(a, dict):
            continue
        raw_score = a.get("sentiment_score")
        kw_score = _keyword_sentiment(a)
        blended = (float(raw_score) * 0.5 + kw_score * 0.5) if raw_score is not None else kw_score
        if blended > 0.15:
            pos += 1
        elif blended < -0.15:
            neg += 1

    score = round((pos - neg) / count, 3)

    if direction == "below" and score <= threshold:
        return {
            "title": f"Sentiment Alert: {symbol} sentiment at {score:+.2f}",
            "message": f"News sentiment for {symbol} has dropped to {score:+.2f} ({neg} negative of {len(articles)} articles), below your threshold of {threshold:+.2f}",
            "severity": "warning",
            "value": score,
        }
    elif direction == "above" and score >= threshold:
        return {
            "title": f"Sentiment Alert: {symbol} sentiment at {score:+.2f}",
            "message": f"News sentiment for {symbol} has risen to {score:+.2f} ({pos} positive of {len(articles)} articles), above your threshold of {threshold:+.2f}",
            "severity": "info",
            "value": score,
        }
    return None


async def _check_earnings_reminder(alert: dict[str, Any]) -> dict[str, Any] | None:
    """Check if earnings are within N days."""
    symbol = alert.get("symbol")
    days_before = int(float(alert.get("threshold", 3)))
    if not symbol:
        return None

    try:
        cal = await data_facade.get_earnings_calendar(weeks=4)
        entries = cal.get("earnings", cal.get("data", []))
        for entry in entries:
            entry_symbol = (entry.get("symbol") or "").upper()
            if entry_symbol == symbol or symbol in entry_symbol:
                date_str = entry.get("date") or entry.get("reportDate")
                if date_str:
                    from datetime import datetime as dt
                    try:
                        report_date = dt.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                        days_until = (report_date - dt.now(timezone.utc)).days
                        if 0 <= days_until <= days_before:
                            return {
                                "title": f"Earnings Reminder: {symbol} in {days_until} days",
                                "message": f"{symbol} earnings expected on {date_str} ({days_until} days away)",
                                "severity": "info",
                                "value": float(days_until),
                            }
                    except ValueError:
                        continue
    except Exception as exc:
        logger.warning("earnings_reminder_check_failed", symbol=symbol, error=str(exc))

    return None
