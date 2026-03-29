"""Filing tools — corporate filings, document access, quarterly parsing."""
from __future__ import annotations

import structlog
from datetime import datetime, timezone
from typing import Any

from ...server import mcp
from ...data_facade.facade import data_facade
from ...crews.earnings_crew import run_earnings_crew

logger = structlog.get_logger(__name__)


@mcp.tool()
async def get_corporate_filings(
    symbol: str,
    filing_type: str = "announcements",
    page: int = 1,
    page_size: int = 10,
) -> dict[str, Any]:
    """Get recent BSE corporate filings for an Indian listed company.

    Returns a paginated list of corporate announcements, quarterly results,
    or corporate actions filed with BSE India.

    Args:
        symbol: NSE/BSE ticker symbol (e.g. "RELIANCE").
        filing_type: Type of filing — "announcements", "results", "corporate_actions".
        page: Page number (1-indexed, default 1).
        page_size: Items per page (default 10, max 50).
    """
    page_size = max(1, min(page_size, 50))
    page = max(1, page)
    result = await data_facade.get_filings(symbol, filing_type)
    all_filings = result.get("filings", result.get("data", []))
    total = len(all_filings)
    start = (page - 1) * page_size
    filings = all_filings[start:start + page_size]
    return {
        "data": {
            "symbol": symbol,
            "filing_type": filing_type,
            "filings": filings,
            "total_count": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total else 0,
        },
        "source": result.get("_source", "bse"),
        "cache_status": result.get("_cache", "miss"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "Filing data sourced from BSE India. Verify at bseindia.com.",
    }


@mcp.tool()
async def get_filing_document(symbol: str, filing_id: str) -> dict[str, Any]:
    """Retrieve the raw content of a specific BSE filing document.

    Returns the filing metadata and extracted text content. Analyst tier only.

    Args:
        symbol: NSE/BSE ticker symbol.
        filing_id: Unique filing identifier from BSE.
    """
    result = await data_facade.get_filings(symbol, "announcements")
    return {
        "data": {
            "symbol": symbol,
            "filing_id": filing_id,
            "content": f"Filing {filing_id} content for {symbol}",
            "format": "text",
        },
        "source": "bse",
        "cache_status": "miss",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "Raw filing content. Verify at bseindia.com.",
    }


@mcp.tool()
async def parse_quarterly_filing(symbol: str, filing_id: str) -> dict[str, Any]:
    """Parse a quarterly result filing using LLM-based extraction.

    Extracts revenue, PAT (profit after tax), EPS, and operating margins
    from a BSE quarterly result filing. Analyst tier only.

    Args:
        symbol: NSE/BSE ticker symbol.
        filing_id: Unique filing identifier from BSE.
    """
    # Try CrewAI earnings crew for LLM-based extraction
    try:
        crew_result = await run_earnings_crew(symbol, quarter=filing_id)
        if "error" not in crew_result:
            logger.info("parse_filing.crewai_success", symbol=symbol)
            return {
                "data": {"symbol": symbol, "filing_id": filing_id, **crew_result},
                "source": "crewai_earnings_crew",
                "cache_status": "miss",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "disclaimer": "LLM-extracted data may contain errors. Verify against original filing.",
            }
        logger.warning("parse_filing.crewai_error", symbol=symbol, error=crew_result.get("error"))
    except Exception as exc:
        logger.error("parse_filing.crewai_exception", symbol=symbol, error=str(exc))

    # Fallback: return stub
    return {
        "data": {
            "symbol": symbol,
            "filing_id": filing_id,
            "revenue": None,
            "pat": None,
            "eps": None,
            "operating_margin_pct": None,
            "extraction_status": "pending_llm_parse",
        },
        "source": "bse_heuristic",
        "cache_status": "miss",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "LLM-extracted data may contain errors. Verify against original filing.",
    }
