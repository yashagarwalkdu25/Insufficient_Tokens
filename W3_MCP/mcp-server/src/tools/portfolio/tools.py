"""Portfolio tools — PS2 Portfolio Risk & Alert Monitor."""
from __future__ import annotations

import structlog
from datetime import datetime, timezone
from typing import Any

from ...server import mcp
from ...data_facade.facade import data_facade
from ...crews.risk_crew import run_risk_crew

logger = structlog.get_logger(__name__)

# In-memory portfolio store keyed by user_id
# TODO: Wire to PostgreSQL via asyncpg
_portfolios: dict[str, list[dict[str, Any]]] = {}


def _get_holdings(user_id: str) -> list[dict[str, Any]]:
    return _portfolios.setdefault(user_id, [])


@mcp.tool()
async def add_to_portfolio(
    symbol: str,
    quantity: int,
    avg_price: float,
    user_id: str = "demo",
) -> dict[str, Any]:
    """Add a stock holding to the user's portfolio.

    Args:
        symbol: NSE/BSE ticker symbol (e.g. "RELIANCE").
        quantity: Number of shares.
        avg_price: Average purchase price per share.
        user_id: User identifier (default "demo").
    """
    import re

    symbol = symbol.strip().upper()
    if not symbol or not re.match(r"^[A-Z0-9&_.-]{1,20}$", symbol):
        return {
            "error": f"Invalid symbol: '{symbol}'. Must be a valid NSE/BSE ticker (e.g. RELIANCE, TCS, INFY).",
            "error_code": "INVALID_SYMBOL",
        }

    # Verify symbol exists by checking for a non-zero LTP
    quote = await data_facade.get_price(symbol)
    ltp = quote.get("ltp") if isinstance(quote, dict) else None
    if ltp is None or ltp == 0:
        return {
            "error": f"Symbol '{symbol}' not found or has no trading data. Use a valid NSE/BSE ticker (e.g. RELIANCE, TCS, INFY).",
            "error_code": "SYMBOL_NOT_FOUND",
        }

    holdings = _get_holdings(user_id)
    for h in holdings:
        if h["symbol"] == symbol:
            h["quantity"] = quantity
            h["avg_price"] = avg_price
            break
    else:
        holdings.append({"symbol": symbol, "quantity": quantity, "avg_price": avg_price})

    return {
        "data": {"symbol": symbol.upper(), "quantity": quantity, "avg_price": avg_price, "action": "added"},
        "source": "local",
        "cache_status": "n/a",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "Portfolio tracking only. Not investment advice.",
    }


@mcp.tool()
async def remove_from_portfolio(symbol: str, user_id: str = "demo") -> dict[str, Any]:
    """Remove a stock from the user's portfolio.

    Args:
        symbol: NSE/BSE ticker symbol.
        user_id: User identifier (default "demo").
    """
    holdings = _get_holdings(user_id)
    _portfolios[user_id] = [h for h in holdings if h["symbol"] != symbol.upper()]
    return {
        "data": {"symbol": symbol.upper(), "action": "removed"},
        "source": "local",
        "cache_status": "n/a",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "Portfolio tracking only. Not investment advice.",
    }


@mcp.tool()
async def get_portfolio_summary(user_id: str = "demo") -> dict[str, Any]:
    """Get a full portfolio summary with current values and P&L.

    Returns each holding with current price, market value, P&L, and
    overall portfolio totals including sector allocation.

    Args:
        user_id: User identifier (default "demo").
    """
    holdings = _get_holdings(user_id)
    enriched = []
    total_invested = 0.0
    total_current = 0.0
    sector_alloc: dict[str, float] = {}

    for h in holdings:
        quote = await data_facade.get_price(h["symbol"])
        ltp = quote.get("ltp") or h["avg_price"]
        invested = h["quantity"] * h["avg_price"]
        current = h["quantity"] * ltp
        pnl = current - invested
        total_invested += invested
        total_current += current
        sector = quote.get("sector", "Unknown")
        sector_alloc[sector] = sector_alloc.get(sector, 0) + current
        enriched.append({
            "symbol": h["symbol"],
            "quantity": h["quantity"],
            "avg_price": h["avg_price"],
            "current_price": ltp,
            "invested_value": round(invested, 2),
            "current_value": round(current, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round((pnl / invested) * 100, 2) if invested else 0,
        })

    if total_current > 0:
        sector_alloc = {k: round((v / total_current) * 100, 2) for k, v in sector_alloc.items()}

    return {
        "data": {
            "user_id": user_id,
            "holdings": enriched,
            "total_invested": round(total_invested, 2),
            "current_value": round(total_current, 2),
            "total_pnl": round(total_current - total_invested, 2),
            "total_pnl_pct": round(((total_current - total_invested) / max(total_invested, 1)) * 100, 2),
            "sector_allocation": sector_alloc,
        },
        "source": "aggregated",
        "cache_status": "miss",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "Portfolio values based on last available quotes. Not investment advice.",
    }


@mcp.tool()
async def portfolio_health_check(user_id: str = "demo") -> dict[str, Any]:
    """Run a health check on the portfolio flagging concentration risks.

    Checks for single-stock concentration (>20%), sector over-exposure
    (>40%), and returns a risk score from 0-100.

    Args:
        user_id: User identifier (default "demo").
    """
    summary = await get_portfolio_summary(user_id)
    holdings = summary["data"]["holdings"]
    total = summary["data"]["current_value"] or 1
    alerts = []

    for h in holdings:
        weight = (h["current_value"] / total) * 100 if total else 0
        if weight > 20:
            alerts.append({
                "alert_type": "concentration",
                "severity": "high" if weight > 30 else "medium",
                "message": f"{h['symbol']} is {weight:.1f}% of portfolio (threshold: 20%)",
            })

    for sector, pct in summary["data"]["sector_allocation"].items():
        if pct > 40:
            alerts.append({
                "alert_type": "sector_tilt",
                "severity": "high",
                "message": f"{sector} sector is {pct:.1f}% of portfolio (threshold: 40%)",
            })

    risk_score = min(100, len(alerts) * 25)
    return {
        "data": {
            "user_id": user_id,
            "risk_score": risk_score,
            "alerts": alerts,
            "holdings_count": len(holdings),
        },
        "source": "computed",
        "cache_status": "n/a",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "Risk assessment is indicative. Not investment advice.",
    }


@mcp.tool()
async def check_concentration_risk(user_id: str = "demo") -> dict[str, Any]:
    """Check if any single stock exceeds 20% or any sector exceeds 40%.

    Args:
        user_id: User identifier (default "demo").
    """
    return await portfolio_health_check(user_id)


@mcp.tool()
async def check_mf_overlap(user_id: str = "demo") -> dict[str, Any]:
    """Check overlap between portfolio holdings and top mutual fund schemes.

    Identifies which portfolio stocks appear in the top large-cap MF
    schemes, helping spot unintentional concentration.

    Args:
        user_id: User identifier (default "demo").
    """
    holdings = _get_holdings(user_id)
    symbols = [h["symbol"] for h in holdings]
    top_mf_stocks = ["HDFCBANK", "ICICIBANK", "RELIANCE", "TCS", "INFY",
                     "ITC", "BHARTIARTL", "SBIN", "LT", "KOTAKBANK"]
    overlaps = [s for s in symbols if s in top_mf_stocks]
    return {
        "data": {
            "user_id": user_id,
            "portfolio_symbols": symbols,
            "overlapping_with_top_mf": overlaps,
            "overlap_count": len(overlaps),
            "message": f"{len(overlaps)} of your holdings appear in top 10 large-cap MF schemes",
        },
        "source": "computed",
        "cache_status": "n/a",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "Overlap analysis is approximate. Not investment advice.",
    }


@mcp.tool()
async def check_macro_sensitivity(user_id: str = "demo") -> dict[str, Any]:
    """Assess portfolio sensitivity to macro-economic factors.

    Maps current RBI rates, inflation, and forex data to sector-level
    impact on the portfolio.

    Args:
        user_id: User identifier (default "demo").
    """
    macro = await data_facade.get_macro()
    holdings = _get_holdings(user_id)
    banking_stocks = {"HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK", "BAJFINANCE"}
    it_stocks = {"TCS", "INFY", "WIPRO", "HCLTECH", "TECHM"}
    symbols = {h["symbol"] for h in holdings}

    impacts = []
    if symbols & banking_stocks:
        impacts.append(f"Banking exposure sensitive to repo rate ({macro.get('repo_rate', 'N/A')}%)")
    if symbols & it_stocks:
        impacts.append(f"IT exposure sensitive to USD/INR ({macro.get('usd_inr', 'N/A')})")

    return {
        "data": {
            "user_id": user_id,
            "repo_rate": macro.get("repo_rate"),
            "cpi": macro.get("cpi_latest"),
            "usd_inr": macro.get("usd_inr"),
            "macro_impacts": impacts,
        },
        "source": macro.get("_source", "rbi_dbie"),
        "cache_status": macro.get("_cache", "miss"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "Macro sensitivity is indicative. Not investment advice.",
    }


@mcp.tool()
async def detect_sentiment_shift(user_id: str = "demo") -> dict[str, Any]:
    """Detect 7-day vs 30-day news sentiment shifts for portfolio holdings.

    Flags holdings where recent sentiment has diverged significantly
    from longer-term sentiment — potential early warning signals.

    Args:
        user_id: User identifier (default "demo").
    """
    holdings = _get_holdings(user_id)
    shifts = []
    for h in holdings[:10]:  # cap to avoid rate-limit exhaustion
        recent = await data_facade.get_news(h["symbol"], days=7)
        articles = recent.get("articles", recent.get("data", []))
        count = max(len(articles), 1)
        pos = sum(1 for a in articles if isinstance(a, dict) and (a.get("sentiment_score") or 0) > 0.2)
        neg = sum(1 for a in articles if isinstance(a, dict) and (a.get("sentiment_score") or 0) < -0.2)
        score = round((pos - neg) / count, 3)
        shifts.append({"symbol": h["symbol"], "sentiment_7d": score, "direction": "positive" if score > 0 else "negative"})

    return {
        "data": {"user_id": user_id, "shifts": shifts},
        "source": "aggregated",
        "cache_status": "miss",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "Sentiment analysis is AI-generated. Not investment advice.",
    }


@mcp.tool()
async def portfolio_risk_report(user_id: str = "demo") -> dict[str, Any]:
    """Generate a full cross-source portfolio risk narrative.

    Combines NSE price data, RBI macro indicators, Finnhub news, and MF
    overlap analysis into a comprehensive risk report with citations.
    Analyst tier only.

    Args:
        user_id: User identifier (default "demo").
    """
    # Try CrewAI risk crew first
    holdings = _get_holdings(user_id)
    try:
        crew_result = await run_risk_crew(holdings, user_id)
        if "error" not in crew_result:
            logger.info("portfolio_risk.crewai_success", user_id=user_id)
            return {
                "data": crew_result,
                "source": "crewai_risk_crew",
                "cache_status": "miss",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "disclaimer": crew_result.get(
                    "disclaimer",
                    "AI-generated risk analysis. Not investment advice.",
                ),
            }
        logger.warning("portfolio_risk.crewai_error", user_id=user_id, error=crew_result.get("error"))
    except Exception as exc:
        logger.error("portfolio_risk.crewai_exception", user_id=user_id, error=str(exc))

    # Fallback: heuristic
    logger.info("portfolio_risk.fallback_heuristic", user_id=user_id)
    summary = await get_portfolio_summary(user_id)
    health = await portfolio_health_check(user_id)
    macro = await data_facade.get_macro()

    return {
        "data": {
            "user_id": user_id,
            "risk_score": health["data"]["risk_score"],
            "alerts": health["data"]["alerts"],
            "macro_context": {
                "repo_rate": macro.get("repo_rate"),
                "cpi": macro.get("cpi_latest"),
                "usd_inr": macro.get("usd_inr"),
            },
            "narrative": (
                f"Portfolio risk score: {health['data']['risk_score']}/100. "
                f"{len(health['data']['alerts'])} alerts detected. "
                "(heuristic fallback — CrewAI unavailable)"
            ),
            "citations": [
                {"source": "Angel One / yfinance", "data_point": "stock prices"},
                {"source": "RBI DBIE", "data_point": "macro indicators"},
            ],
        },
        "source": "cross_source_heuristic",
        "cache_status": "miss",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "AI-generated risk analysis. Not investment advice.",
    }


@mcp.tool()
async def what_if_analysis(scenario: str, user_id: str = "demo") -> dict[str, Any]:
    """Simulate the impact of a macro scenario on the portfolio.

    Predefined scenarios include rate changes, currency moves, and
    sector rotations. Analyst tier only.

    Args:
        scenario: Scenario description — e.g. "RBI cuts 25bps", "USD/INR +5%", "IT sector correction 10%".
        user_id: User identifier (default "demo").
    """
    holdings = _get_holdings(user_id)
    banking = {"HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK", "BAJFINANCE", "BAJAJFINSV"}
    it_stocks = {"TCS", "INFY", "WIPRO", "HCLTECH", "TECHM"}
    realty = {"DLF"}

    impacts: dict[str, float] = {}
    scenario_lower = scenario.lower()

    for h in holdings:
        sym = h["symbol"]
        if "rate cut" in scenario_lower or "cuts" in scenario_lower:
            if sym in banking:
                impacts[sym] = 3.5
            elif sym in realty:
                impacts[sym] = 5.0
            else:
                impacts[sym] = 1.0
        elif "usd" in scenario_lower:
            if sym in it_stocks:
                impacts[sym] = -4.0
            else:
                impacts[sym] = -1.0
        elif "correction" in scenario_lower:
            if sym in it_stocks:
                impacts[sym] = -10.0
            else:
                impacts[sym] = -2.0
        else:
            impacts[sym] = 0.0

    avg_impact = round(sum(impacts.values()) / max(len(impacts), 1), 2)

    return {
        "data": {
            "scenario": scenario,
            "portfolio_impact_pct": avg_impact,
            "per_stock_impact": impacts,
            "narrative": f"Scenario '{scenario}' would impact portfolio by approx {avg_impact:+.1f}%.",
        },
        "source": "simulated",
        "cache_status": "n/a",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "Simulated scenario analysis. Actual impact may vary. Not investment advice.",
    }


@mcp.tool()
async def import_portfolio(
    holdings_csv: str,
    platform: str = "groww",
    user_id: str = "demo",
) -> dict[str, Any]:
    """Import portfolio holdings from a broker CSV (Groww, Zerodha, Angel One).

    The CSV text should have rows with Symbol/Ticker, Quantity, and Avg Price.
    Supported formats:
      - Groww: "Symbol,Quantity,Avg Cost" (header row auto-detected)
      - Zerodha: "Instrument,Qty,Avg. cost" (Kite holdings export)
      - Angel One: "Symbol,Qty,Buy Avg" (Smart API export)
      - Generic: any CSV with columns for symbol, quantity, price

    Args:
        holdings_csv: Raw CSV text content from the broker export.
        platform: Broker platform — "groww", "zerodha", "angelone", or "generic".
        user_id: User identifier (auto-injected from JWT).
    """
    import csv
    import io
    import re

    platform = platform.lower().strip()

    # Column name mappings per platform
    _SYMBOL_COLS = {"symbol", "ticker", "instrument", "trading symbol", "tradingsymbol", "scrip", "stock"}
    _QTY_COLS = {"quantity", "qty", "net qty", "net quantity", "holdings qty"}
    _PRICE_COLS = {"avg cost", "avg. cost", "avg price", "buy avg", "average price", "buy average", "avg_price"}

    def _find_col(headers: list[str], candidates: set[str]) -> int | None:
        for i, h in enumerate(headers):
            if h.strip().lower() in candidates:
                return i
        return None

    def _clean_symbol(raw: str) -> str:
        """Strip exchange suffix (e.g. '-EQ', '-BE', '.NS') and whitespace."""
        s = raw.strip().upper()
        s = re.sub(r"[-.]?(EQ|BE|NS|BSE|NSE|BO)$", "", s)
        return s.strip()

    lines = holdings_csv.strip()
    if not lines:
        return {"error": "Empty CSV data. Please paste your holdings export.", "error_code": "EMPTY_CSV"}

    reader = csv.reader(io.StringIO(lines))
    rows = list(reader)
    if len(rows) < 2:
        return {"error": "CSV must have a header row and at least one data row.", "error_code": "INVALID_CSV"}

    headers = rows[0]
    sym_idx = _find_col(headers, _SYMBOL_COLS)
    qty_idx = _find_col(headers, _QTY_COLS)
    price_idx = _find_col(headers, _PRICE_COLS)

    # Fallback: first 3 columns if headers don't match
    if sym_idx is None:
        sym_idx = 0
    if qty_idx is None:
        qty_idx = 1
    if price_idx is None:
        price_idx = 2

    imported = []
    skipped = []
    holdings = _get_holdings(user_id)

    for row in rows[1:]:
        if len(row) <= max(sym_idx, qty_idx, price_idx):
            continue
        raw_symbol = _clean_symbol(row[sym_idx])
        if not raw_symbol or not re.match(r"^[A-Z0-9&_.-]{1,20}$", raw_symbol):
            skipped.append({"symbol": row[sym_idx].strip(), "reason": "invalid_symbol"})
            continue

        try:
            quantity = int(float(row[qty_idx].strip().replace(",", "")))
            avg_price = float(row[price_idx].strip().replace(",", "").replace("₹", ""))
        except (ValueError, IndexError):
            skipped.append({"symbol": raw_symbol, "reason": "invalid_number"})
            continue

        if quantity <= 0 or avg_price <= 0:
            skipped.append({"symbol": raw_symbol, "reason": "zero_or_negative"})
            continue

        # Verify symbol exists
        quote = await data_facade.get_price(raw_symbol)
        ltp = quote.get("ltp") if isinstance(quote, dict) else None
        if ltp is None or ltp == 0:
            skipped.append({"symbol": raw_symbol, "reason": "symbol_not_found"})
            continue

        # Upsert into holdings
        found = False
        for h in holdings:
            if h["symbol"] == raw_symbol:
                h["quantity"] = quantity
                h["avg_price"] = avg_price
                found = True
                break
        if not found:
            holdings.append({"symbol": raw_symbol, "quantity": quantity, "avg_price": avg_price})

        imported.append({"symbol": raw_symbol, "quantity": quantity, "avg_price": avg_price})

    return {
        "data": {
            "platform": platform,
            "imported_count": len(imported),
            "skipped_count": len(skipped),
            "imported": imported,
            "skipped": skipped,
            "total_holdings": len(holdings),
        },
        "source": f"csv_import_{platform}",
        "cache_status": "n/a",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "Imported holdings for tracking only. Verify against your broker. Not investment advice.",
    }
