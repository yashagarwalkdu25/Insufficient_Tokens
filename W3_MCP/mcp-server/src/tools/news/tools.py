"""News and sentiment tools — company news, sentiment scoring, market news."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ...server import mcp
from ...data_facade.facade import data_facade


@mcp.tool()
async def get_company_news(
    symbol: str, days: int = 7, page: int = 1, page_size: int = 10,
) -> dict[str, Any]:
    """Get recent news articles for an Indian listed company.

    Returns a paginated list of news articles with title, source, URL,
    publication date, and optional summary. Sources: Finnhub, GNews.

    Args:
        symbol: NSE/BSE ticker symbol (e.g. "RELIANCE", "TCS").
        days: Look-back window in days (default 7, max 30).
        page: Page number (1-indexed, default 1).
        page_size: Articles per page (default 10, max 50).
    """
    page_size = max(1, min(page_size, 50))
    page = max(1, page)
    result = await data_facade.get_news(symbol, min(days, 30))
    all_articles = result.get("articles", result.get("data", []))
    total = len(all_articles)
    start = (page - 1) * page_size
    articles = all_articles[start:start + page_size]
    return {
        "data": {
            "symbol": symbol,
            "days": days,
            "articles": articles,
            "total_count": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total else 0,
        },
        "source": result.get("_source", "unknown"),
        "cache_status": result.get("_cache", "miss"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "For informational purposes only. Not investment advice.",
    }


@mcp.tool()
async def get_news_sentiment(symbol: str, days: int = 7) -> dict[str, Any]:
    """Compute aggregated news sentiment score for a stock.

    Analyses recent news and returns a sentiment score from -1.0 (very
    bearish) to +1.0 (very bullish), article counts, and whether the
    sentiment is company-specific or driven by sector/macro factors.

    Args:
        symbol: NSE/BSE ticker symbol.
        days: Look-back window in days (default 7).
    """
    result = await data_facade.get_news(symbol, min(days, 30))
    articles = result.get("articles", result.get("data", []))

    positive = sum(1 for a in articles if isinstance(a, dict) and (a.get("sentiment_score") or 0) > 0.2)
    negative = sum(1 for a in articles if isinstance(a, dict) and (a.get("sentiment_score") or 0) < -0.2)
    neutral = len(articles) - positive - negative
    total = max(len(articles), 1)
    score = round((positive - negative) / total, 3)

    return {
        "data": {
            "symbol": symbol,
            "overall_score": score,
            "article_count": len(articles),
            "positive_count": positive,
            "negative_count": negative,
            "neutral_count": neutral,
            "driver_type": "company_specific",
        },
        "source": result.get("_source", "unknown"),
        "cache_status": result.get("_cache", "miss"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "Sentiment scores are AI-generated approximations. Not investment advice.",
    }


@mcp.tool()
async def get_market_news(
    category: str = "business", page: int = 1, page_size: int = 10,
) -> dict[str, Any]:
    """Get broad Indian financial market news.

    Returns paginated top headlines for the given category — useful for
    building a morning brief or sector scan.

    Args:
        category: News category — "business", "technology", "economy".
        page: Page number (1-indexed, default 1).
        page_size: Articles per page (default 10, max 50).
    """
    page_size = max(1, min(page_size, 50))
    page = max(1, page)
    result = await data_facade.get_news(f"India {category}", days=1)
    all_articles = result.get("articles", result.get("data", []))
    total = len(all_articles)
    start = (page - 1) * page_size
    articles = all_articles[start:start + page_size]
    return {
        "data": {
            "category": category,
            "articles": articles,
            "total_count": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total else 0,
        },
        "source": result.get("_source", "unknown"),
        "cache_status": result.get("_cache", "miss"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "For informational purposes only. Not investment advice.",
    }
