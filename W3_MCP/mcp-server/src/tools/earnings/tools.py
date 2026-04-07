"""Earnings tools — PS3 Earnings Season Command Center.

All 15 PS3 tools:
  Free:     get_earnings_calendar, get_past_results_dates
  Premium:  get_eps_history, get_pre_earnings_profile, get_analyst_expectations,
            get_post_results_reaction, compare_actual_vs_expected, get_option_chain
  Analyst:  earnings_verdict, earnings_season_dashboard, compare_quarterly_performance
"""
from __future__ import annotations

import structlog
from datetime import datetime, timezone
from typing import Any

from ...server import mcp
from ...data_facade.facade import data_facade
from ...data_facade.isin_mapper import isin_mapper, _NIFTY_50 as _NIFTY_50_RAW
from ...crews.earnings_crew import run_earnings_crew
from ...cross_source import compute_trust_envelope

logger = structlog.get_logger(__name__)


def _synthetic_earnings_signals(payload: dict[str, Any]) -> list[dict[str, Any]]:
    verdict = payload.get("beat_miss") or "inline"
    beat_dir = 0.75 if verdict == "beat" else (-0.75 if verdict == "miss" else 0.0)
    mr = payload.get("market_reaction") or {}
    try:
        change_pct = float(mr.get("price_change_pct") or 0)
    except (TypeError, ValueError):
        change_pct = 0.0
    pr_dir = 0.55 if change_pct > 1 else (-0.55 if change_pct < -1 else 0.0)
    ss = payload.get("shareholding_signal") or {}
    fii = ss.get("fii_change_pp")
    sh_dir = 0.0
    if fii is not None:
        try:
            fv = float(fii)
            sh_dir = 0.45 if fv > 0.5 else (-0.45 if fv < -0.5 else 0.0)
        except (TypeError, ValueError):
            pass
    try:
        sent = float(payload.get("sentiment_score") or 0)
    except (TypeError, ValueError):
        sent = 0.0
    return [
        {"source": "results", "signal_type": "earnings_beat_miss", "direction": beat_dir, "confidence": 0.75},
        {"source": "market", "signal_type": "post_results_reaction", "direction": pr_dir, "confidence": 0.8},
        {"source": "shareholding", "signal_type": "shareholding_change", "direction": sh_dir, "confidence": 0.65},
        {"source": "news", "signal_type": "guidance_sentiment", "direction": sent, "confidence": 0.55},
    ]


def _attach_trust_earnings(data: dict[str, Any]) -> None:
    sigs = data.get("signals")
    if not isinstance(sigs, list) or len(sigs) == 0:
        sigs = _synthetic_earnings_signals(data)
    ctr = data.get("contradictions")
    extra = list(ctr) if isinstance(ctr, list) else None
    data.update(
        compute_trust_envelope(
            sigs,
            context="earnings",
            extra_contradiction_strings=extra,
        )
    )

# Known NSE symbols for India-filtering (superset of isin_mapper)
_INDIAN_SYMBOLS: set[str] = {
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR", "ITC",
    "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "AXISBANK", "BAJFINANCE", "MARUTI",
    "HCLTECH", "TITAN", "SUNPHARMA", "TATAMOTORS", "WIPRO", "NESTLEIND",
    "BAJAJFINSV", "DRREDDY", "TECHM", "ADANIENT", "ADANIPORTS", "POWERGRID",
    "NTPC", "ULTRACEMCO", "ONGC", "COALINDIA", "JSWSTEEL", "TATASTEEL",
    "GRASIM", "CIPLA", "DIVISLAB", "BPCL", "HEROMOTOCO", "EICHERMOT",
    "SHRIRAMFIN", "APOLLOHOSP", "M&M", "BRITANNIA", "INDUSINDBK", "HINDALCO",
    "TATACONSUM", "SBILIFE", "HDFCLIFE", "BAJAJ-AUTO", "ASIANPAINT", "DLF",
    # Additional large / mid caps
    "VEDL", "BANKBARODA", "PNB", "IOC", "GAIL", "PIDILITIND", "GODREJCP",
    "DABUR", "MARICO", "HAVELLS", "VOLTAS", "TRENT", "IRCTC", "ZOMATO",
    "PAYTM", "NYKAA", "DELHIVERY", "POLICYBZR", "HAL", "BEL", "RECLTD",
    "PFC", "NHPC", "IRFC", "SJVN", "CANBK", "UNIONBANK", "FEDERALBNK",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_quarterly_eps(symbol: str) -> list[dict[str, Any]]:
    """Fetch quarterly earnings from yfinance and compute YoY/QoQ."""
    from ...data_facade.adapters.yfinance_adapter import YFinanceAdapter
    adapter = YFinanceAdapter()
    raw = await adapter.get_quarterly_earnings(symbol)
    quarters = raw.get("quarterly_earnings", [])
    enriched: list[dict[str, Any]] = []
    for i, q in enumerate(quarters):
        eps = q.get("eps")
        prev_q_eps = quarters[i - 1].get("eps") if i > 0 else None
        prev_y_eps = quarters[i - 4].get("eps") if i >= 4 else None
        qoq = round((eps - prev_q_eps) / abs(prev_q_eps) * 100, 2) if eps is not None and prev_q_eps else None
        yoy = round((eps - prev_y_eps) / abs(prev_y_eps) * 100, 2) if eps is not None and prev_y_eps else None
        enriched.append({**q, "qoq_pct": qoq, "yoy_pct": yoy})
    return enriched


# ---------------------------------------------------------------------------
# FREE-TIER TOOLS
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_earnings_calendar(
    weeks: int = 2,
    filter: str = "india",
    portfolio_symbols: str = "",
) -> dict[str, Any]:
    """Get upcoming earnings announcement dates for Indian companies.

    Returns a list of companies expected to report results in the next
    N weeks, enriched with company names, exchange, and sector. Entries
    are filtered to Indian NSE/BSE stocks by default.

    Args:
        weeks: Number of weeks to look ahead (default 2, max 8).
        filter: Filter mode — "india" (default), "nifty50", "portfolio", or "all".
        portfolio_symbols: Comma-separated symbols to highlight (auto-injected for portfolio filter).
    """
    from datetime import timedelta

    result = await data_facade.get_earnings_calendar(min(weeks, 8))
    raw_entries = result.get("earnings", result.get("data", []))

    # Build portfolio set for highlighting
    portfolio_set: set[str] = set()
    if portfolio_symbols:
        portfolio_set = {s.strip().upper() for s in portfolio_symbols.split(",") if s.strip()}

    # Nifty 50 set from isin_mapper
    nifty50_set = {m["nse"].upper() for m in _NIFTY_50_RAW}

    now = datetime.now(timezone.utc)
    enriched: list[dict[str, Any]] = []

    seen_symbols: set[str] = set()

    for entry in raw_entries:
        sym = (entry.get("symbol") or "").strip().upper()
        if sym.endswith(".NS") or sym.endswith(".BO"):
            sym = sym[:-3]
        if not sym:
            continue

        origin = entry.get("_origin", "")
        is_from_bse = origin == "bse"

        # BSE entries are always Indian
        is_indian = is_from_bse or sym in _INDIAN_SYMBOLS or isin_mapper.resolve(sym) is not None

        # Filter logic
        if filter == "india" and not is_indian:
            continue
        if filter == "nifty50" and sym not in nifty50_set:
            continue
        if filter == "portfolio" and sym not in portfolio_set:
            continue

        # Deduplicate: prefer BSE data for Indian stocks
        if sym in seen_symbols:
            continue
        seen_symbols.add(sym)

        # Enrich with company name, sector, exchange
        mapping = isin_mapper.resolve(sym)
        company_name = entry.get("company_name") or (mapping.company_name if mapping else "")
        sector = mapping.sector if mapping else ""
        exchange = entry.get("exchange") or ("NSE" if mapping or is_indian else "")
        bse_code = entry.get("scrip_code") or (mapping.bse_scrip_code if mapping else "")

        # Parse date and compute countdown
        raw_date = entry.get("date") or entry.get("expected_date") or ""
        date_tbd = not raw_date or raw_date.lower() in ("tbd", "n/a", "")
        days_away: int | None = None
        week_group = "TBD"

        if not date_tbd:
            try:
                dt = datetime.strptime(raw_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                delta = (dt - now).days
                days_away = max(0, delta)
                if delta < 0:
                    week_group = "Past"
                elif delta <= 7:
                    week_group = "This Week"
                elif delta <= 14:
                    week_group = "Next Week"
                else:
                    week_group = f"In {delta // 7} Weeks"
            except ValueError:
                date_tbd = True

        # BSE/NSE verification links
        nse_url = f"https://www.nseindia.com/get-quotes/equity?symbol={sym}" if is_indian else ""
        bse_url = f"https://www.bseindia.com/stock-share-price/{bse_code}" if bse_code else ""

        enriched.append({
            "symbol": sym,
            "company_name": company_name,
            "sector": sector,
            "exchange": exchange,
            "expected_date": raw_date if not date_tbd else None,
            "date_tbd": date_tbd,
            "tbd_reason": "Date not yet published by the data provider. Check BSE/NSE announcements." if date_tbd else None,
            "days_away": days_away,
            "week_group": week_group,
            "quarter": entry.get("quarter"),
            "year": entry.get("year"),
            "eps_estimate": entry.get("epsEstimate"),
            "eps_actual": entry.get("epsActual"),
            "revenue_estimate": entry.get("revenueEstimate"),
            "in_portfolio": sym in portfolio_set,
            "is_nifty50": sym in nifty50_set,
            "data_source": "BSE" if is_from_bse else "Finnhub",
            "verify_links": {
                "nse": nse_url,
                "bse": bse_url,
            } if (nse_url or bse_url) else None,
        })

    # Sort: portfolio first, then by date (TBD last)
    def _sort_key(e: dict) -> tuple:
        return (
            0 if e["in_portfolio"] else 1,
            0 if not e["date_tbd"] else 1,
            e.get("expected_date") or "9999-99-99",
        )
    enriched.sort(key=_sort_key)

    return {
        "data": {
            "weeks": weeks,
            "filter": filter,
            "total_count": len(enriched),
            "entries": enriched,
        },
        "source": result.get("_source", "finnhub"),
        "cache_status": result.get("_cache", "miss"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "Earnings dates are estimates and may change. Verify with BSE/NSE.",
    }


@mcp.tool()
async def get_past_results_dates(symbol: str) -> dict[str, Any]:
    """Get historical quarterly results announcement dates for a company.

    Args:
        symbol: NSE/BSE ticker symbol (e.g. "TCS").
    """
    result = await data_facade.get_filings(symbol, "results")
    return {
        "data": {
            "symbol": symbol,
            "past_dates": result.get("filings", result.get("data", [])),
        },
        "source": result.get("_source", "bse"),
        "cache_status": result.get("_cache", "miss"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "Historical data sourced from BSE India.",
    }


# ---------------------------------------------------------------------------
# PREMIUM-TIER TOOLS
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_eps_history(symbol: str, quarters: int = 8) -> dict[str, Any]:
    """Get quarterly EPS history with YoY and QoQ growth trends.

    Returns EPS values for the last N quarters along with revenue,
    quarter-over-quarter growth, and year-over-year growth percentages.

    Args:
        symbol: NSE/BSE ticker symbol.
        quarters: Number of quarters (default 8).
    """
    eps_data = await _get_quarterly_eps(symbol)
    # Trim to requested count (most recent N)
    trimmed = eps_data[-quarters:] if len(eps_data) > quarters else eps_data

    latest_eps = trimmed[-1].get("eps") if trimmed else None
    avg_yoy = None
    yoy_vals = [q["yoy_pct"] for q in trimmed if q.get("yoy_pct") is not None]
    if yoy_vals:
        avg_yoy = round(sum(yoy_vals) / len(yoy_vals), 2)

    return {
        "data": {
            "symbol": symbol,
            "quarters_requested": quarters,
            "quarters_available": len(trimmed),
            "eps_history": trimmed,
            "latest_eps": latest_eps,
            "avg_yoy_growth_pct": avg_yoy,
        },
        "source": "yfinance",
        "cache_status": "miss",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "EPS data sourced from yfinance. Verify with company filings.",
    }


@mcp.tool()
async def get_pre_earnings_profile(symbol: str) -> dict[str, Any]:
    """Get a comprehensive pre-earnings profile for a company.

    Combines: last 4 quarters of EPS + revenue, key ratios, shareholding
    trend (FII buy/sell), options activity (PCR, max pain), and recent
    news sentiment. Ideal for earnings prep.

    Args:
        symbol: NSE/BSE ticker symbol.
    """
    fundamentals, shareholding, news = await data_facade.get_fundamentals(symbol), \
        await data_facade.get_shareholding(symbol, quarters=4), \
        await data_facade.get_news(symbol, days=7)

    # Quarterly EPS history (last 4)
    eps_data = await _get_quarterly_eps(symbol)
    last_4q = eps_data[-4:] if len(eps_data) >= 4 else eps_data

    # Options activity summary
    from ...data_facade.adapters.yfinance_adapter import YFinanceAdapter
    adapter = YFinanceAdapter()
    options_raw = await adapter.get_options(symbol)
    options_summary = {
        "pcr": options_raw.get("pcr"),
        "max_pain": options_raw.get("max_pain"),
        "total_call_oi": options_raw.get("total_call_oi", 0),
        "total_put_oi": options_raw.get("total_put_oi", 0),
        "expiry": options_raw.get("expiry"),
    }

    # FII buy/sell signal from shareholding entries
    entries = shareholding.get("entries", shareholding.get("data", {}).get("entries", []))
    fii_trend = "stable"
    if len(entries) >= 2:
        latest_fii = entries[-1].get("fii", 0) if isinstance(entries[-1], dict) else 0
        prev_fii = entries[-2].get("fii", 0) if isinstance(entries[-2], dict) else 0
        diff = latest_fii - prev_fii
        if diff > 0.5:
            fii_trend = f"increasing (+{diff:.1f}pp)"
        elif diff < -0.5:
            fii_trend = f"decreasing ({diff:.1f}pp)"

    # News sentiment
    articles = news.get("articles", news.get("data", []))
    count = max(len(articles), 1)
    pos = sum(1 for a in articles if isinstance(a, dict) and (a.get("sentiment_score") or 0) > 0.2)
    neg = sum(1 for a in articles if isinstance(a, dict) and (a.get("sentiment_score") or 0) < -0.2)
    sentiment = round((pos - neg) / count, 3)

    return {
        "data": {
            "symbol": symbol,
            "last_4_quarters": last_4q,
            "key_ratios": {
                "pe_ratio": fundamentals.get("pe_ratio"),
                "pb_ratio": fundamentals.get("pb_ratio"),
                "roe": fundamentals.get("roe"),
                "debt_to_equity": fundamentals.get("debt_to_equity"),
                "eps": fundamentals.get("eps"),
                "dividend_yield": fundamentals.get("dividend_yield"),
            },
            "shareholding_trend": {
                "fii_trend": fii_trend,
                "entries": entries[-4:] if isinstance(entries, list) else [],
            },
            "options_activity": options_summary,
            "news_sentiment_score": sentiment,
            "news_articles_count": len(articles),
        },
        "source": "aggregated",
        "cache_status": "miss",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "Pre-earnings profile is AI-aggregated. Not investment advice.",
    }


@mcp.tool()
async def get_analyst_expectations(symbol: str) -> dict[str, Any]:
    """Get analyst consensus estimates or extrapolated estimates for upcoming earnings.

    Uses historical EPS growth rate extrapolation when free-tier API
    consensus data is unavailable for Indian stocks.

    Args:
        symbol: NSE/BSE ticker symbol.
    """
    eps_data = await _get_quarterly_eps(symbol)
    fundamentals = await data_facade.get_fundamentals(symbol)

    actual_eps = fundamentals.get("eps")
    yoy_vals = [q["yoy_pct"] for q in eps_data if q.get("yoy_pct") is not None]
    avg_growth = round(sum(yoy_vals) / len(yoy_vals), 2) if yoy_vals else 10.0

    # Extrapolate next quarter EPS
    extrapolated_eps = round(actual_eps * (1 + avg_growth / 100), 2) if actual_eps else None

    # Extrapolate revenue from last known quarter
    last_rev = eps_data[-1].get("revenue") if eps_data else None
    extrapolated_rev = round(last_rev * (1 + avg_growth / 100)) if last_rev else None

    return {
        "data": {
            "symbol": symbol,
            "consensus_eps": extrapolated_eps,
            "consensus_revenue": extrapolated_rev,
            "growth_rate_used_pct": avg_growth,
            "num_analysts": 0,
            "source_type": "extrapolated_from_history",
            "basis_eps": actual_eps,
            "basis_quarters": len(yoy_vals),
        },
        "source": "yfinance_extrapolated",
        "cache_status": "miss",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "Estimates extrapolated from historical growth. Not consensus. Not investment advice.",
    }


@mcp.tool()
async def get_post_results_reaction(symbol: str, filing_date: str = "") -> dict[str, Any]:
    """Get stock price reaction around a quarterly results announcement.

    Returns price changes on the result day, day+1, day+2 and volume
    spike detection using historical price data.

    Args:
        symbol: NSE/BSE ticker symbol.
        filing_date: Date of result announcement in YYYY-MM-DD (empty = use recent data).
    """
    from ...data_facade.adapters.yfinance_adapter import YFinanceAdapter
    adapter = YFinanceAdapter()

    hist = await adapter.get_historical(symbol, period="1mo", interval="1d")
    bars = hist.get("bars", [])
    quote = await data_facade.get_price(symbol)

    # Find filing_date index or use the last 3 bars
    day0 = day1 = day2 = None
    avg_vol = 0
    vol_spike_pct = None

    if bars and len(bars) >= 3:
        if filing_date:
            idx = next((i for i, b in enumerate(bars) if b["date"] == filing_date), None)
        else:
            idx = len(bars) - 3  # Assume 3rd-to-last bar is "result day"

        if idx is not None and idx < len(bars):
            day0 = bars[idx]
            day1 = bars[idx + 1] if idx + 1 < len(bars) else None
            day2 = bars[idx + 2] if idx + 2 < len(bars) else None

        # Average volume of 20 bars before result
        pre_bars = bars[max(0, (idx or 0) - 20):(idx or 0)]
        if pre_bars:
            avg_vol = sum(b["volume"] for b in pre_bars) / len(pre_bars)
            if day0 and avg_vol > 0:
                vol_spike_pct = round((day0["volume"] - avg_vol) / avg_vol * 100, 1)

    def _bar_change(bar: dict | None, prev_close: float | None) -> float | None:
        if bar is None or prev_close is None or prev_close == 0:
            return None
        return round((bar["close"] - prev_close) / prev_close * 100, 2)

    prev_close_d0 = bars[(idx or 0) - 1]["close"] if bars and (idx or 0) > 0 else None

    return {
        "data": {
            "symbol": symbol,
            "filing_date": filing_date or (day0["date"] if day0 else "unknown"),
            "price_on_result_day": day0["close"] if day0 else quote.get("ltp"),
            "price_change_day0_pct": _bar_change(day0, prev_close_d0),
            "price_change_day1_pct": _bar_change(day1, day0["close"] if day0 else None),
            "price_change_day2_pct": _bar_change(day2, day1["close"] if day1 else None),
            "cumulative_3day_pct": (
                round(((day2 or day1 or day0 or {}).get("close", 0) - (prev_close_d0 or 0)) / max(prev_close_d0 or 1, 1) * 100, 2)
                if prev_close_d0 and (day2 or day1 or day0) else None
            ),
            "volume_result_day": day0["volume"] if day0 else None,
            "avg_volume_prior_20d": round(avg_vol) if avg_vol else None,
            "volume_spike_pct": vol_spike_pct,
        },
        "source": "yfinance",
        "cache_status": "miss",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "Post-results reaction data. Not investment advice.",
    }


@mcp.tool()
async def compare_actual_vs_expected(symbol: str) -> dict[str, Any]:
    """Compare actual quarterly results against extrapolated expectations.

    Returns a beat/miss/inline verdict with the surprise percentage.
    Uses historical EPS trend extrapolation for expected values.

    Args:
        symbol: NSE/BSE ticker symbol.
    """
    eps_data = await _get_quarterly_eps(symbol)
    fundamentals = await data_facade.get_fundamentals(symbol)

    actual_eps = fundamentals.get("eps")

    # Extrapolated expectation: average YoY growth applied to year-ago quarter
    expected_eps = None
    if len(eps_data) >= 5:
        year_ago_eps = eps_data[-5].get("eps")
        yoy_vals = [q["yoy_pct"] for q in eps_data if q.get("yoy_pct") is not None]
        avg_growth = sum(yoy_vals) / len(yoy_vals) if yoy_vals else 0
        if year_ago_eps is not None:
            expected_eps = round(year_ago_eps * (1 + avg_growth / 100), 2)

    # If we can't extrapolate, fall back to previous quarter
    if expected_eps is None and eps_data:
        expected_eps = eps_data[-1].get("eps")

    surprise_pct = 0.0
    verdict = "inline"
    if actual_eps is not None and expected_eps and expected_eps != 0:
        surprise_pct = round((actual_eps - expected_eps) / abs(expected_eps) * 100, 2)
        if surprise_pct > 5:
            verdict = "beat"
        elif surprise_pct < -5:
            verdict = "miss"

    return {
        "data": {
            "symbol": symbol,
            "verdict": verdict,
            "actual_eps": actual_eps,
            "expected_eps": expected_eps,
            "surprise_pct": surprise_pct,
            "estimation_method": "yoy_growth_extrapolation",
        },
        "source": "yfinance_computed",
        "cache_status": "miss",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "Beat/miss analysis uses extrapolated estimates. Verify with official filings.",
    }


@mcp.tool()
async def get_option_chain(symbol: str, expiry: str = "") -> dict[str, Any]:
    """Get the option chain for a stock — strike-wise OI, LTP, IV.

    Returns call and put data for each strike price, including open
    interest, last traded price, implied volatility, PCR, and max pain.

    Args:
        symbol: NSE/BSE ticker symbol.
        expiry: Expiry date in YYYY-MM-DD format (empty = nearest expiry).
    """
    from ...data_facade.adapters.yfinance_adapter import YFinanceAdapter
    adapter = YFinanceAdapter()
    options = await adapter.get_options(symbol)

    if options.get("error"):
        return {
            "data": {
                "symbol": symbol,
                "expiry": expiry or "nearest",
                "calls": [],
                "puts": [],
                "pcr": None,
                "max_pain": None,
                "note": "Options data unavailable for this symbol",
            },
            "source": "yfinance",
            "cache_status": "miss",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "disclaimer": "Option data for educational purposes only. Not investment advice.",
        }

    return {
        "data": {
            "symbol": symbol,
            "expiry": options.get("expiry", "nearest"),
            "calls": options.get("calls", []),
            "puts": options.get("puts", []),
            "pcr": options.get("pcr"),
            "max_pain": options.get("max_pain"),
            "total_call_oi": options.get("total_call_oi", 0),
            "total_put_oi": options.get("total_put_oi", 0),
        },
        "source": "yfinance",
        "cache_status": "miss",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "Option data for educational purposes only. Not investment advice.",
    }


# ---------------------------------------------------------------------------
# ANALYST-TIER TOOLS (Cross-Source Reasoning)
# ---------------------------------------------------------------------------

@mcp.tool()
async def earnings_verdict(symbol: str) -> dict[str, Any]:
    """Generate a full cross-source earnings verdict.

    Combines: BSE filing data, NSE price reaction, shareholding changes,
    news sentiment, and estimates into a comprehensive earnings narrative
    with citations. Analyst tier only.

    Args:
        symbol: NSE/BSE ticker symbol.
    """
    # Try CrewAI earnings crew first
    try:
        crew_result = await run_earnings_crew(symbol)
        if "error" not in crew_result:
            logger.info("earnings_verdict.crewai_success", symbol=symbol)
            _attach_trust_earnings(crew_result)
            return {
                "data": crew_result,
                "source": "crewai_earnings_crew",
                "cache_status": "miss",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "disclaimer": crew_result.get(
                    "disclaimer",
                    "AI-generated earnings analysis. Not investment advice.",
                ),
            }
        logger.warning("earnings_verdict.crewai_error", symbol=symbol, error=crew_result.get("error"))
    except Exception as exc:
        logger.error("earnings_verdict.crewai_exception", symbol=symbol, error=str(exc))

    # Fallback: rich cross-source heuristic
    logger.info("earnings_verdict.fallback_heuristic", symbol=symbol)

    # Resolve symbol to NSE-suffixed ticker for yfinance
    mapping = isin_mapper.resolve(symbol)
    yf_symbol = mapping.nse_symbol if mapping else symbol

    fundamentals = await data_facade.get_fundamentals(symbol)
    quote = await data_facade.get_price(symbol)
    news = await data_facade.get_news(symbol, days=7)
    shareholding = await data_facade.get_shareholding(symbol, quarters=2)
    eps_data = await _get_quarterly_eps(yf_symbol)

    # Log which sources succeeded/failed for debugging
    fund_ok = "error" not in fundamentals
    quote_ok = "error" not in quote
    news_ok = "error" not in news
    sh_ok = "error" not in shareholding
    logger.info(
        "earnings_verdict.source_status",
        symbol=symbol,
        fundamentals=fund_ok,
        quote=quote_ok,
        news=news_ok,
        shareholding=sh_ok,
        eps_quarters=len(eps_data),
    )

    actual_eps = fundamentals.get("eps") if fund_ok else None
    expected_eps = None
    if len(eps_data) >= 5:
        year_ago = eps_data[-5].get("eps")
        yoy_vals = [q["yoy_pct"] for q in eps_data if q.get("yoy_pct") is not None]
        avg_g = sum(yoy_vals) / len(yoy_vals) if yoy_vals else 0
        if year_ago:
            expected_eps = round(year_ago * (1 + avg_g / 100), 2)
    surprise_pct = round((actual_eps - expected_eps) / abs(expected_eps) * 100, 2) if actual_eps and expected_eps and expected_eps != 0 else 0
    verdict_label = "beat" if surprise_pct > 5 else ("miss" if surprise_pct < -5 else "inline")

    # Shareholding FII change
    sh_entries = []
    if sh_ok:
        sh_entries = shareholding.get("entries", shareholding.get("data", {}).get("entries", []))
    fii_change = None
    if len(sh_entries) >= 2 and isinstance(sh_entries[-1], dict) and isinstance(sh_entries[-2], dict):
        fii_change = round(sh_entries[-1].get("fii", 0) - sh_entries[-2].get("fii", 0), 2)

    # News sentiment — handle both finnhub (has sentiment_score) and gnews (no score)
    articles: list[dict[str, Any]] = []
    if news_ok:
        articles = news.get("articles", news.get("data", []))
    article_count = len(articles)

    # If articles lack sentiment_score, approximate from headline keywords
    sentiment = 0.0
    if article_count > 0:
        pos = neg = 0
        for a in articles:
            if not isinstance(a, dict):
                continue
            score = a.get("sentiment_score")
            if score is not None:
                if float(score) > 0.2:
                    pos += 1
                elif float(score) < -0.2:
                    neg += 1
            else:
                text = (a.get("headline") or a.get("title") or "").lower()
                if any(w in text for w in ("beat", "surge", "profit", "growth", "rally", "strong", "record")):
                    pos += 1
                elif any(w in text for w in ("miss", "decline", "loss", "fall", "drop", "weak", "slump")):
                    neg += 1
        sentiment = round((pos - neg) / max(article_count, 1), 3)

    change_pct = quote.get("change_pct", 0) if quote_ok else 0
    try:
        change_pct = float(change_pct or 0)
    except (TypeError, ValueError):
        change_pct = 0.0
    price_dir = "rose" if change_pct > 0 else "fell"
    ltp = quote.get("ltp") if quote_ok else None

    # Build narrative
    narrative_parts: list[str] = []
    if actual_eps is not None:
        part = f"{symbol} reported EPS of ₹{actual_eps}"
        if expected_eps:
            part += f" vs estimated ₹{expected_eps} ({verdict_label}, {surprise_pct:+.1f}% surprise)"
        narrative_parts.append(part)
    else:
        narrative_parts.append(f"{symbol} earnings data is being aggregated from available sources")

    if quote_ok and ltp:
        narrative_parts.append(
            f"[NSE]. Stock {price_dir} {abs(change_pct):.1f}% on results day. LTP ₹{ltp}."
        )

    if fii_change is not None:
        narrative_parts.append(
            f"FII holding {'increased' if fii_change > 0 else 'decreased'} {abs(fii_change):.1f}pp in prior quarter [shareholding data]."
        )

    if article_count > 0:
        sentiment_label = "positive" if sentiment > 0.1 else ("negative" if sentiment < -0.1 else "neutral")
        narrative_parts.append(
            f"News sentiment: {sentiment_label} ({sentiment:+.2f}) from {article_count} articles [news feed]."
        )
    else:
        narrative_parts.append("No recent news articles found for sentiment analysis.")

    # Detect contradictions
    contradictions: list[str] = []
    if verdict_label == "beat" and change_pct < -1:
        contradictions.append("Earnings beat but stock fell — sell-off may be pre-positioned or guidance-driven.")
    if verdict_label == "miss" and change_pct > 1:
        contradictions.append("Earnings miss but stock rose — expectations may have been already priced in.")
    if fii_change is not None and fii_change < -1 and verdict_label == "beat":
        contradictions.append("FII reduced holdings before a beat — possible profit booking ahead of results.")

    # Build citations with data availability notes
    citations: list[dict[str, Any]] = []
    if fund_ok and actual_eps is not None:
        citations.append({"source": "yfinance", "data_point": f"EPS ₹{actual_eps}", "value": str(actual_eps)})
    else:
        citations.append({"source": "yfinance", "data_point": "EPS data unavailable — check symbol or try later"})

    if quote_ok and ltp:
        citations.append({"source": quote.get("_source", "NSE"), "data_point": f"Price ₹{ltp} ({change_pct:+.1f}%)", "value": str(ltp)})
    else:
        citations.append({"source": "NSE", "data_point": "Price data unavailable"})

    if fii_change is not None:
        citations.append({"source": "shareholding", "data_point": f"FII change {fii_change:+.1f}pp"})
    else:
        citations.append({"source": "shareholding", "data_point": "FII data unavailable"})

    news_source = news.get("_source", "news feed") if news_ok else "news feed"
    if article_count > 0:
        citations.append({"source": news_source, "data_point": f"Sentiment {sentiment:+.2f} from {article_count} articles"})
    else:
        citations.append({"source": news_source, "data_point": "No recent articles found"})

    ev_data: dict[str, Any] = {
        "symbol": symbol,
        "quarter": "latest",
        "beat_miss": verdict_label,
        "surprise_pct": surprise_pct,
        "filing_highlights": {
            "eps": actual_eps,
            "expected_eps": expected_eps,
            "revenue": fundamentals.get("revenue") if fund_ok else None,
            "pe_ratio": fundamentals.get("pe_ratio") if fund_ok else None,
        },
        "market_reaction": {
            "price_change_pct": change_pct,
            "price": ltp,
        },
        "shareholding_signal": {
            "fii_change_pp": fii_change,
        },
        "sentiment_score": sentiment,
        "contradictions": contradictions,
        "narrative": " ".join(narrative_parts),
        "citations": citations,
    }
    _attach_trust_earnings(ev_data)

    return {
        "data": ev_data,
        "source": "cross_source_heuristic",
        "cache_status": "miss",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "AI-generated earnings analysis. Not investment advice.",
    }


@mcp.tool()
async def earnings_season_dashboard(week_date: str = "") -> dict[str, Any]:
    """Get an earnings season summary — who beat, who missed, sector trends.

    Aggregates data from the earnings calendar and cross-references with
    actual EPS data to produce beat/miss counts and sector trends.
    Analyst tier only.

    Args:
        week_date: Week date in YYYY-MM-DD format (empty = current week).
    """
    calendar = await data_facade.get_earnings_calendar(weeks=4)
    entries = calendar.get("earnings", calendar.get("data", []))

    # Extract unique symbols from the real calendar (Indian stocks only)
    calendar_symbols: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        sym = (entry.get("symbol") or "").strip().upper()
        if sym.endswith(".NS") or sym.endswith(".BO"):
            sym = sym[:-3]
        if not sym or sym in seen:
            continue
        is_indian = sym in _INDIAN_SYMBOLS or isin_mapper.resolve(sym) is not None
        if is_indian:
            seen.add(sym)
            calendar_symbols.append(sym)

    # Cap at 30 to avoid excessive API calls
    analyse_symbols = calendar_symbols[:30]

    beats = misses = inlines = 0
    analysed = 0
    sector_data: dict[str, dict[str, int]] = {}
    notable: list[dict[str, Any]] = []

    for sym in analyse_symbols:
        try:
            fund = await data_facade.get_fundamentals(sym)
            if "error" in fund:
                continue
            sector = fund.get("sector") or "Unknown"
            if sector not in sector_data:
                sector_data[sector] = {"beats": 0, "misses": 0, "inlines": 0}

            eps_data = await _get_quarterly_eps(sym)
            if not eps_data:
                continue
            analysed += 1
            yoy_vals = [q["yoy_pct"] for q in eps_data if q.get("yoy_pct") is not None]
            avg_g = sum(yoy_vals) / len(yoy_vals) if yoy_vals else 0

            if avg_g > 5:
                beats += 1
                sector_data[sector]["beats"] += 1
                if avg_g > 15:
                    notable.append({"symbol": sym, "type": "positive_surprise", "yoy_growth_pct": round(avg_g, 1)})
            elif avg_g < -5:
                misses += 1
                sector_data[sector]["misses"] += 1
                if avg_g < -15:
                    notable.append({"symbol": sym, "type": "negative_surprise", "yoy_growth_pct": round(avg_g, 1)})
            else:
                inlines += 1
                sector_data[sector]["inlines"] += 1
        except Exception as exc:
            logger.warning("season_dashboard.symbol_error", symbol=sym, error=str(exc))
            continue

    return {
        "data": {
            "week_date": week_date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "companies_analysed": analysed,
            "beats": beats,
            "misses": misses,
            "inlines": inlines,
            "sector_trends": sector_data,
            "notable_surprises": notable,
            "calendar_entries": len(entries),
        },
        "source": "aggregated",
        "cache_status": "miss",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "Earnings season dashboard is AI-aggregated. Not investment advice.",
    }


@mcp.tool()
async def compare_quarterly_performance(symbols: str) -> dict[str, Any]:
    """Compare quarterly performance side-by-side for 2-4 companies.

    Returns: EPS, revenue, key ratios, margin trends, shareholding changes,
    and recent price reaction for each company. Analyst tier only.

    Args:
        symbols: Comma-separated ticker symbols (e.g. "TCS,INFY,WIPRO").
    """
    symbol_list = [s.strip().upper() for s in symbols.split(",")][:4]
    results: dict[str, Any] = {}

    for sym in symbol_list:
        fund = await data_facade.get_fundamentals(sym)
        quote = await data_facade.get_price(sym)
        shareholding = await data_facade.get_shareholding(sym, quarters=2)
        eps_data = await _get_quarterly_eps(sym)

        # FII change
        entries = shareholding.get("entries", shareholding.get("data", {}).get("entries", []))
        fii_change = None
        if len(entries) >= 2 and isinstance(entries[-1], dict) and isinstance(entries[-2], dict):
            fii_change = round(entries[-1].get("fii", 0) - entries[-2].get("fii", 0), 2)

        # Latest YoY growth
        latest_yoy = eps_data[-1].get("yoy_pct") if eps_data and eps_data[-1].get("yoy_pct") is not None else None

        results[sym] = {
            "eps": fund.get("eps"),
            "revenue": fund.get("revenue"),
            "pe_ratio": fund.get("pe_ratio"),
            "pb_ratio": fund.get("pb_ratio"),
            "roe": fund.get("roe"),
            "debt_to_equity": fund.get("debt_to_equity"),
            "market_cap": fund.get("market_cap"),
            "price": quote.get("ltp"),
            "price_change_pct": quote.get("change_pct"),
            "eps_yoy_growth_pct": latest_yoy,
            "fii_change_pp": fii_change,
            "sector": fund.get("sector"),
        }

    return {
        "data": {
            "symbols": symbol_list,
            "comparison": results,
        },
        "source": "aggregated",
        "cache_status": "miss",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "Comparative analysis is AI-aggregated. Not investment advice.",
    }
