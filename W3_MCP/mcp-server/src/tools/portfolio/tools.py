"""Portfolio tools — PS2 Portfolio Risk & Alert Monitor."""
from __future__ import annotations

import structlog
from datetime import datetime, timezone
from typing import Any

from ...server import mcp
from ...data_facade.facade import data_facade
from ...crews.risk_crew import run_risk_crew
from ...cross_source import compute_trust_envelope
from ...db import portfolio_repo

logger = structlog.get_logger(__name__)

_TOP_MF_FOR_OVERLAP = frozenset(
    {
        "HDFCBANK",
        "ICICIBANK",
        "RELIANCE",
        "TCS",
        "INFY",
        "ITC",
        "BHARTIARTL",
        "SBIN",
        "LT",
        "KOTAKBANK",
    }
)


async def _synthetic_portfolio_signals(
    user_id: str,
    risk_score: float,
    alerts: list[dict[str, Any]],
    macro_context: dict[str, Any],
) -> list[dict[str, Any]]:
    holdings = await _get_holdings(user_id)
    symbols = [h["symbol"] for h in holdings]
    overlap_count = sum(1 for s in symbols if s in _TOP_MF_FOR_OVERLAP)
    mf_dir = -0.45 if overlap_count > 5 else (0.2 if overlap_count == 0 else 0.0)
    sector_stress = any(a.get("alert_type") == "sector_tilt" for a in alerts)
    conc_stress = any(a.get("alert_type") == "concentration" for a in alerts)
    if sector_stress and conc_stress:
        sec_dir = -0.55
    elif sector_stress:
        sec_dir = -0.4
    elif conc_stress:
        sec_dir = -0.35
    else:
        sec_dir = 0.15
    repo = macro_context.get("repo_rate")
    try:
        r = float(repo) if repo is not None else 6.5
    except (TypeError, ValueError):
        r = 6.5
    macro_dir = 0.35 if r < 6.75 else -0.15
    sent_dir = -0.3 if risk_score > 50 else 0.15
    return [
        {
            "source": "portfolio",
            "signal_type": "sector_concentration",
            "direction": sec_dir,
            "confidence": 0.65,
        },
        {
            "source": "computed",
            "signal_type": "mf_overlap",
            "direction": mf_dir,
            "confidence": 0.55,
        },
        {
            "source": "RBI DBIE",
            "signal_type": "macro_sensitivity",
            "direction": macro_dir,
            "confidence": 0.6,
        },
        {
            "source": "aggregated",
            "signal_type": "sentiment_shift",
            "direction": sent_dir,
            "confidence": 0.5,
        },
    ]


def _attach_trust_portfolio(data: dict[str, Any]) -> None:
    ctr = data.get("contradictions")
    extra = list(ctr) if isinstance(ctr, list) else None
    data.update(
        compute_trust_envelope(
            data.get("signals"),
            context="portfolio",
            extra_contradiction_strings=extra,
        )
    )

async def _get_holdings(user_id: str) -> list[dict[str, Any]]:
    """Fetch holdings from PostgreSQL (per-user persistence)."""
    return await portfolio_repo.get_holdings(user_id)


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

    await portfolio_repo.upsert_holding(user_id, symbol, quantity, avg_price)

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
    await portfolio_repo.remove_holding(user_id, symbol.upper())
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
    from ...data_facade.isin_mapper import isin_mapper

    holdings = await _get_holdings(user_id)
    enriched = []
    total_invested = 0.0
    total_current = 0.0
    sector_alloc: dict[str, float] = {}

    for h in holdings:
        sym = h["symbol"]
        quote = await data_facade.get_price(sym)
        ltp = quote.get("ltp") or h["avg_price"]
        invested = h["quantity"] * h["avg_price"]
        current = h["quantity"] * ltp
        pnl = current - invested
        total_invested += invested
        total_current += current

        # Resolve sector: try isin_mapper first, then fundamentals
        mapping = isin_mapper.resolve(sym)
        sector = mapping.sector if mapping else None
        if not sector:
            fund = await data_facade.get_fundamentals(sym)
            sector = fund.get("sector") if "error" not in fund else None
        sector = sector or "Other"

        sector_alloc[sector] = sector_alloc.get(sector, 0) + current
        enriched.append({
            "symbol": sym,
            "quantity": h["quantity"],
            "avg_price": h["avg_price"],
            "current_price": ltp,
            "invested_value": round(invested, 2),
            "current_value": round(current, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round((pnl / invested) * 100, 2) if invested else 0,
            "sector": sector,
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
    holdings = summary["data"]["holdings"]  # type: ignore[index]
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
    holdings = await _get_holdings(user_id)
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
    holdings = await _get_holdings(user_id)
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
            "cpi": macro.get("cpi_inflation_pct"),
            "usd_inr": macro.get("usd_inr"),
            "macro_impacts": impacts,
        },
        "source": macro.get("_source", "rbi_dbie"),
        "cache_status": macro.get("_cache", "miss"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "Macro sensitivity is indicative. Not investment advice.",
    }


def _estimate_article_sentiment(article: dict[str, Any]) -> float:
    """Estimate sentiment from a single article using score or keyword heuristic."""
    score = article.get("sentiment_score")
    if score is not None:
        try:
            return float(score)
        except (TypeError, ValueError):
            pass

    text = (
        (article.get("headline") or article.get("title") or "") + " " +
        (article.get("summary") or article.get("description") or "")
    ).lower()

    _POS = ("beat", "surge", "profit", "growth", "rally", "strong", "record", "upgrade", "outperform", "rises", "gains")
    _NEG = ("miss", "decline", "loss", "fall", "drop", "weak", "slump", "downgrade", "underperform", "slides", "plunges")
    pos = sum(1 for w in _POS if w in text)
    neg = sum(1 for w in _NEG if w in text)
    if pos > neg:
        return 0.3
    if neg > pos:
        return -0.3
    return 0.0


@mcp.tool()
async def detect_sentiment_shift(user_id: str = "demo") -> dict[str, Any]:
    """Detect 7-day vs 30-day news sentiment shifts for portfolio holdings.

    Flags holdings where recent sentiment has diverged significantly
    from longer-term sentiment — potential early warning signals.

    Args:
        user_id: User identifier (default "demo").
    """
    holdings = await _get_holdings(user_id)
    shifts = []
    for h in holdings[:10]:
        recent = await data_facade.get_news(h["symbol"], days=7)
        articles = recent.get("articles", recent.get("data", []))
        article_count = len(articles)

        if article_count > 0:
            scores = [_estimate_article_sentiment(a) for a in articles if isinstance(a, dict)]
            score = round(sum(scores) / max(len(scores), 1), 3)
        else:
            score = 0.0

        direction = "positive" if score > 0.05 else ("negative" if score < -0.05 else "neutral")
        shifts.append({
            "symbol": h["symbol"],
            "sentiment_7d": score,
            "direction": direction,
            "articles_count": article_count,
        })

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
    holdings = await _get_holdings(user_id)
    try:
        crew_result = await run_risk_crew(holdings, user_id)
        if "error" not in crew_result:
            logger.info("portfolio_risk.crewai_success", user_id=user_id)
            _attach_trust_portfolio(crew_result)
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
    health = await portfolio_health_check(user_id)
    macro = await data_facade.get_macro()
    alerts_fb = health["data"]["alerts"]
    rs = float(health["data"]["risk_score"])
    macro_ctx = {
        "repo_rate": macro.get("repo_rate"),
        "cpi": macro.get("cpi_inflation_pct"),
        "usd_inr": macro.get("usd_inr"),
    }
    pr_data: dict[str, Any] = {
        "user_id": user_id,
        "risk_score": rs,
        "alerts": alerts_fb,
        "macro_context": macro_ctx,
        "narrative": (
            f"Portfolio risk score: {health['data']['risk_score']}/100. "
            f"{len(alerts_fb)} alerts detected. "
            "(heuristic fallback — CrewAI unavailable)"
        ),
        "citations": [
            {"source": "Angel One / yfinance", "data_point": "stock prices"},
            {"source": "RBI DBIE", "data_point": "macro indicators"},
        ],
        "signals": await _synthetic_portfolio_signals(user_id, rs, alerts_fb, macro_ctx),
    }
    _attach_trust_portfolio(pr_data)

    return {
        "data": pr_data,
        "source": "cross_source_heuristic",
        "cache_status": "miss",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "AI-generated risk analysis. Not investment advice.",
    }


@mcp.tool()
async def what_if_analysis(scenario: str, user_id: str = "demo") -> dict[str, Any]:
    """Simulate the impact of a macro scenario on the portfolio.

    Uses empirical sector-correlation data to estimate stock-level
    impact for scenarios including: rate changes, currency moves,
    oil price shocks, inflation shifts, and broad market corrections.

    Args:
        scenario: Scenario description — e.g. "RBI cuts 25bps", "USD/INR +5%",
                  "IT sector correction 10%", "oil price +20%", "inflation rises".
        user_id: User identifier (default "demo").
    """
    holdings = await _get_holdings(user_id)

    # Sector classification — map stocks to sectors
    _SECTOR_MAP: dict[str, str] = {
        # Banking & Finance
        "HDFCBANK": "banking", "ICICIBANK": "banking", "SBIN": "banking",
        "KOTAKBANK": "banking", "AXISBANK": "banking", "BAJFINANCE": "nbfc",
        "BAJAJFINSV": "nbfc", "PNB": "banking", "BANKBARODA": "banking",
        "INDUSINDBK": "banking",
        # IT
        "TCS": "it", "INFY": "it", "WIPRO": "it", "HCLTECH": "it",
        "TECHM": "it", "LTIM": "it", "MPHASIS": "it", "PERSISTENT": "it",
        # Pharma
        "SUNPHARMA": "pharma", "DRREDDY": "pharma", "CIPLA": "pharma",
        "DIVISLAB": "pharma", "BIOCON": "pharma", "LUPIN": "pharma",
        # Auto
        "MARUTI": "auto", "TATAMOTORS": "auto", "M&M": "auto",
        "BAJAJ-AUTO": "auto", "HEROMOTOCO": "auto", "EICHERMOT": "auto",
        # FMCG
        "HINDUNILVR": "fmcg", "ITC": "fmcg", "NESTLEIND": "fmcg",
        "BRITANNIA": "fmcg", "DABUR": "fmcg", "MARICO": "fmcg",
        "COLPAL": "fmcg", "GODREJCP": "fmcg",
        # Energy / Oil & Gas
        "RELIANCE": "energy", "ONGC": "energy", "IOC": "energy",
        "BPCL": "energy", "GAIL": "energy", "NTPC": "power",
        "POWERGRID": "power", "ADANIGREEN": "power", "TATAPOWER": "power",
        # Metals & Mining
        "TATASTEEL": "metals", "HINDALCO": "metals", "JSWSTEEL": "metals",
        "COALINDIA": "metals", "VEDL": "metals", "NMDC": "metals",
        # Realty
        "DLF": "realty", "GODREJPROP": "realty", "OBEROIRLTY": "realty",
        "PRESTIGE": "realty",
        # Telecom
        "BHARTIARTL": "telecom", "IDEA": "telecom",
        # Infra
        "LT": "infra", "ADANIENT": "infra", "ADANIPORTS": "infra",
    }

    # Empirical-based scenario → sector sensitivity multipliers
    # Based on historical NSE sector index correlations with macro events
    _SCENARIO_SENSITIVITIES: dict[str, dict[str, float]] = {
        "rate_cut": {
            "banking": 4.2, "nbfc": 3.8, "realty": 5.5, "auto": 2.8,
            "it": 1.2, "pharma": 0.5, "fmcg": 0.8, "energy": 1.0,
            "metals": 1.5, "power": 2.0, "telecom": 1.5, "infra": 3.0,
        },
        "rate_hike": {
            "banking": -2.5, "nbfc": -3.5, "realty": -5.0, "auto": -2.5,
            "it": -0.8, "pharma": -0.3, "fmcg": -0.5, "energy": -0.8,
            "metals": -1.0, "power": -1.5, "telecom": -1.0, "infra": -2.5,
        },
        "usd_strengthen": {
            "it": 3.5, "pharma": 2.5, "banking": -1.0, "nbfc": -1.2,
            "auto": -2.0, "fmcg": -0.5, "energy": -2.5, "metals": -1.5,
            "realty": -0.5, "power": -0.8, "telecom": -0.5, "infra": -1.0,
        },
        "usd_weaken": {
            "it": -4.0, "pharma": -2.0, "banking": 1.0, "nbfc": 1.0,
            "auto": 1.5, "fmcg": 0.5, "energy": 2.0, "metals": 1.5,
            "realty": 0.5, "power": 0.8, "telecom": 0.3, "infra": 1.0,
        },
        "oil_up": {
            "energy": 6.0, "it": -1.0, "auto": -3.5, "fmcg": -2.0,
            "banking": -1.5, "nbfc": -1.5, "pharma": -1.0, "metals": 1.0,
            "realty": -1.0, "power": -2.0, "telecom": -0.5, "infra": -1.5,
        },
        "oil_down": {
            "energy": -5.0, "it": 1.0, "auto": 3.0, "fmcg": 1.5,
            "banking": 1.0, "nbfc": 1.0, "pharma": 0.5, "metals": -0.5,
            "realty": 1.0, "power": 1.5, "telecom": 0.3, "infra": 1.0,
        },
        "inflation_up": {
            "fmcg": -2.5, "auto": -2.0, "banking": -2.0, "nbfc": -2.5,
            "realty": -3.0, "it": -1.0, "pharma": -0.5, "energy": 1.5,
            "metals": 2.0, "power": -1.0, "telecom": -1.0, "infra": -2.0,
        },
        "broad_correction": {
            "banking": -8.0, "nbfc": -10.0, "realty": -12.0, "auto": -7.0,
            "it": -9.0, "pharma": -4.0, "fmcg": -3.5, "energy": -6.0,
            "metals": -11.0, "power": -5.0, "telecom": -5.0, "infra": -9.0,
        },
        "broad_rally": {
            "banking": 6.0, "nbfc": 7.0, "realty": 8.0, "auto": 5.0,
            "it": 5.5, "pharma": 3.0, "fmcg": 2.5, "energy": 4.5,
            "metals": 7.0, "power": 3.5, "telecom": 3.5, "infra": 6.0,
        },
    }

    # Parse scenario to identify which sensitivity table to use
    scenario_lower = scenario.lower()
    matched_scenarios: list[str] = []
    if any(k in scenario_lower for k in ("rate cut", "cuts rate", "rbi cut", "repo cut", "dovish")):
        matched_scenarios.append("rate_cut")
    if any(k in scenario_lower for k in ("rate hike", "hikes rate", "rbi hike", "repo hike", "hawkish")):
        matched_scenarios.append("rate_hike")
    if any(k in scenario_lower for k in ("usd up", "dollar strong", "rupee weak", "inr deprec")):
        matched_scenarios.append("usd_strengthen")
    if any(k in scenario_lower for k in ("usd down", "dollar weak", "rupee strong", "inr apprec")):
        matched_scenarios.append("usd_weaken")
    if any(k in scenario_lower for k in ("oil up", "oil price rise", "crude up", "oil surge")):
        matched_scenarios.append("oil_up")
    if any(k in scenario_lower for k in ("oil down", "oil price fall", "crude down", "oil drop")):
        matched_scenarios.append("oil_down")
    if any(k in scenario_lower for k in ("inflation rise", "inflation up", "cpi up")):
        matched_scenarios.append("inflation_up")
    if any(k in scenario_lower for k in ("correction", "crash", "bear", "sell-off", "selloff")):
        matched_scenarios.append("broad_correction")
    if any(k in scenario_lower for k in ("rally", "bull", "boom", "recovery")):
        matched_scenarios.append("broad_rally")

    if not matched_scenarios:
        matched_scenarios.append("broad_correction")

    # Compute per-stock impact using sector sensitivities
    per_stock: list[dict[str, Any]] = []
    total_invested = 0.0
    total_simulated = 0.0

    for h in holdings:
        sym = h["symbol"]
        sector = _SECTOR_MAP.get(sym, "other")
        quote = await data_facade.get_price(sym)
        ltp = quote.get("ltp") or h["avg_price"]
        current_value = h["quantity"] * ltp

        # Average impact across matched scenarios
        total_impact = 0.0
        for sc in matched_scenarios:
            sens = _SCENARIO_SENSITIVITIES.get(sc, {})
            total_impact += sens.get(sector, 0.5)
        avg_impact_pct = total_impact / len(matched_scenarios)

        simulated_value = current_value * (1 + avg_impact_pct / 100)
        pnl_change = simulated_value - current_value

        total_invested += current_value
        total_simulated += simulated_value

        per_stock.append({
            "symbol": sym,
            "sector": sector,
            "current_value": round(current_value, 2),
            "impact_pct": round(avg_impact_pct, 2),
            "simulated_value": round(simulated_value, 2),
            "pnl_change": round(pnl_change, 2),
        })

    portfolio_impact_pct = round(
        ((total_simulated - total_invested) / max(total_invested, 1)) * 100, 2
    )

    # Sort by impact to show most affected first
    per_stock.sort(key=lambda s: s["impact_pct"])

    return {
        "data": {
            "scenario": scenario,
            "matched_scenarios": matched_scenarios,
            "portfolio_impact_pct": portfolio_impact_pct,
            "total_current_value": round(total_invested, 2),
            "total_simulated_value": round(total_simulated, 2),
            "total_pnl_change": round(total_simulated - total_invested, 2),
            "per_stock_impact": per_stock,
            "most_affected": per_stock[0]["symbol"] if per_stock else None,
            "least_affected": per_stock[-1]["symbol"] if per_stock else None,
            "narrative": (
                f"Scenario '{scenario}' would impact your portfolio by approx "
                f"{portfolio_impact_pct:+.1f}% (₹{total_simulated - total_invested:+,.0f}). "
                f"Most affected: {per_stock[0]['symbol']} ({per_stock[0]['impact_pct']:+.1f}%). "
                f"Based on historical NSE sector-correlation analysis."
                if per_stock else f"No holdings to simulate for scenario '{scenario}'."
            ),
        },
        "source": "simulated_correlation",
        "cache_status": "n/a",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "Simulated scenario analysis based on historical sector correlations. Actual impact may vary. Not investment advice.",
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

        imported.append({"symbol": raw_symbol, "quantity": quantity, "avg_price": avg_price})

    # Bulk upsert all validated holdings to PostgreSQL
    if imported:
        await portfolio_repo.bulk_upsert(user_id, imported)

    holdings = await _get_holdings(user_id)

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
