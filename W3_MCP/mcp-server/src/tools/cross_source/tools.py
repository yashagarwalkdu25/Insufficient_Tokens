"""Cross-source reasoning tools — PS1 Analyst-tier multi-API synthesis."""
from __future__ import annotations

import structlog
from datetime import datetime, timezone
from typing import Any

from ...server import mcp
from ...data_facade.facade import data_facade
from ...crews.research_crew import run_research_crew

logger = structlog.get_logger(__name__)


@mcp.tool()
async def cross_reference_signals(symbol: str) -> dict[str, Any]:
    """Generate a cross-source signal matrix for a stock.

    Pulls data from 4+ sources (Angel One, Alpha Vantage, Finnhub, BSE,
    RBI DBIE) and produces a matrix of directional signals with confidence
    scores. Explicitly detects contradictions (e.g. price falling but
    fundamentals improving). Analyst tier only.

    Args:
        symbol: NSE/BSE ticker symbol (e.g. "RELIANCE").
    """
    import re

    # --- Symbol validation ---
    symbol = symbol.strip().upper()
    if not symbol or not re.match(r"^[A-Z0-9&_.-]{1,20}$", symbol):
        return {
            "error": f"Invalid symbol: '{symbol}'. Must be a valid NSE/BSE ticker (e.g. RELIANCE, TCS, INFY).",
            "error_code": "INVALID_SYMBOL",
        }

    # Quick check: try to get a quote first to verify symbol exists
    quote_check = await data_facade.get_price(symbol)
    ltp = quote_check.get("ltp") if isinstance(quote_check, dict) else None
    if ltp is None or ltp == 0:
        return {
            "error": f"Symbol '{symbol}' not found or has no trading data. Use a valid NSE/BSE ticker (e.g. RELIANCE, TCS, INFY).",
            "error_code": "SYMBOL_NOT_FOUND",
        }

    # Try CrewAI research crew first (real multi-agent reasoning)
    try:
        crew_result = await run_research_crew(symbol)
        if "error" not in crew_result:
            logger.info("cross_reference.crewai_success", symbol=symbol)
            return {
                "data": crew_result,
                "source": "crewai_research_crew",
                "cache_status": "miss",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "disclaimer": crew_result.get(
                    "disclaimer",
                    "This analysis is AI-generated from multiple data sources. "
                    "It does not constitute investment advice. Verify independently.",
                ),
            }
        logger.warning("cross_reference.crewai_error", symbol=symbol, error=crew_result.get("error"))
    except Exception as exc:
        logger.error("cross_reference.crewai_exception", symbol=symbol, error=str(exc))

    # Fallback: deterministic heuristic analysis from data facade
    logger.info("cross_reference.fallback_heuristic", symbol=symbol)
    quote = await data_facade.get_price(symbol)
    fundamentals = await data_facade.get_fundamentals(symbol)
    news = await data_facade.get_news(symbol, days=7)
    macro = await data_facade.get_macro()

    articles = news.get("articles", news.get("data", []))
    count = max(len(articles), 1)
    pos = sum(1 for a in articles if isinstance(a, dict) and (a.get("sentiment_score") or 0) > 0.2)
    neg = sum(1 for a in articles if isinstance(a, dict) and (a.get("sentiment_score") or 0) < -0.2)
    sentiment_score = round((pos - neg) / count, 3)

    change_pct = quote.get("change_pct") or 0
    price_direction = 0.5 if change_pct > 1 else (-0.5 if change_pct < -1 else 0.0)
    fund_direction = 0.6 if (fundamentals.get("roe") or 0) > 15 else 0.0
    macro_direction = 0.4 if (macro.get("repo_rate") or 7) < 7 else 0.0

    signals = [
        {
            "source": quote.get("_source", "Angel One"),
            "signal_type": "price",
            "direction": price_direction,
            "confidence": 0.8,
            "evidence": f"LTP ₹{quote.get('ltp', 'N/A')} ({change_pct:+.1f}% today)",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        {
            "source": fundamentals.get("_source", "Alpha Vantage"),
            "signal_type": "fundamental",
            "direction": fund_direction,
            "confidence": 0.7,
            "evidence": f"ROE: {fundamentals.get('roe', 'N/A')}%, P/E: {fundamentals.get('pe_ratio', 'N/A')}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        {
            "source": news.get("_source", "Finnhub"),
            "signal_type": "sentiment",
            "direction": sentiment_score,
            "confidence": 0.6,
            "evidence": f"Sentiment: {sentiment_score:+.2f} from {len(articles)} articles",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        {
            "source": macro.get("_source", "RBI DBIE"),
            "signal_type": "macro",
            "direction": macro_direction,
            "confidence": 0.5,
            "evidence": f"Repo rate: {macro.get('repo_rate', 'N/A')}%, CPI: {macro.get('cpi_latest', 'N/A')}%",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    ]

    contradictions = []
    if price_direction < 0 and fund_direction > 0:
        contradictions.append(
            "Price declining but fundamentals positive — may indicate sector/macro headwinds, not company issues"
        )
    if sentiment_score < -0.2 and fund_direction > 0:
        contradictions.append(
            "Negative news sentiment despite strong fundamentals — news may be driven by broader market fears"
        )

    avg_confidence = round(sum(s["confidence"] for s in signals) / len(signals), 3)

    return {
        "data": {
            "symbol": symbol,
            "signals": signals,
            "contradictions": contradictions,
            "synthesis": (
                f"Cross-source analysis for {symbol}: {len(signals)} signals from "
                f"{len(set(s['source'] for s in signals))} sources. "
                f"{'Contradictions detected.' if contradictions else 'Signals broadly aligned.'} "
                f"(heuristic fallback — CrewAI unavailable)"
            ),
            "overall_confidence": avg_confidence,
            "citations": [
                {"source": s["source"], "data_point": s["evidence"], "value": str(s["direction"]),
                 "timestamp": s["timestamp"]}
                for s in signals
            ],
        },
        "source": "cross_source_heuristic",
        "cache_status": "miss",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": (
            "This analysis is AI-generated from multiple data sources. "
            "It does not constitute investment advice. Verify independently."
        ),
    }


@mcp.tool()
async def generate_research_brief(symbol: str) -> dict[str, Any]:
    """Generate a full research brief with source citations.

    Produces a comprehensive research note combining price data,
    fundamentals, news sentiment, shareholding patterns, and macro
    context — each claim cited to its source. Analyst tier only.

    Args:
        symbol: NSE/BSE ticker symbol (e.g. "RELIANCE").
    """
    # Try CrewAI research crew first
    try:
        crew_result = await run_research_crew(symbol)
        if "error" not in crew_result:
            shareholding = await data_facade.get_shareholding(symbol, quarters=2)
            logger.info("research_brief.crewai_success", symbol=symbol)
            return {
                "data": {
                    "symbol": symbol,
                    "title": f"Research Brief: {symbol}",
                    "signals": crew_result.get("signals", []),
                    "contradictions": crew_result.get("contradictions", []),
                    "shareholding_snapshot": shareholding.get("data", {}),
                    "synthesis": crew_result.get("synthesis", ""),
                    "overall_confidence": crew_result.get("overall_confidence", 0.5),
                    "citations": crew_result.get("citations", []),
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                },
                "source": "crewai_research_crew",
                "cache_status": "miss",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "disclaimer": crew_result.get(
                    "disclaimer",
                    "AI-generated research brief from multiple sources. "
                    "Not investment advice. Verify all data independently.",
                ),
            }
        logger.warning("research_brief.crewai_error", symbol=symbol, error=crew_result.get("error"))
    except Exception as exc:
        logger.error("research_brief.crewai_exception", symbol=symbol, error=str(exc))

    # Fallback to heuristic cross-source + shareholding
    logger.info("research_brief.fallback_heuristic", symbol=symbol)
    signals_result = await cross_reference_signals(symbol)
    shareholding = await data_facade.get_shareholding(symbol, quarters=2)

    data = signals_result["data"]

    return {
        "data": {
            "symbol": symbol,
            "title": f"Research Brief: {symbol}",
            "signals": data["signals"],
            "contradictions": data["contradictions"],
            "shareholding_snapshot": shareholding.get("data", {}),
            "synthesis": data["synthesis"],
            "overall_confidence": data["overall_confidence"],
            "citations": data["citations"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "source": "cross_source_heuristic",
        "cache_status": "miss",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": (
            "AI-generated research brief from multiple sources. "
            "Not investment advice. Verify all data independently."
        ),
    }
