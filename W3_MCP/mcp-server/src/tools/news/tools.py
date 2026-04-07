"""News and sentiment tools — company news, diversified sentiment scoring, market news.

Implements multi-dimensional sentiment analysis with:
  - Source credibility weighting (tier 1/2/3 sources)
  - Freshness decay (recent articles count more)
  - Keyword-based sentiment enrichment
  - Information quality scoring (source agreement, freshness, diversity)
"""
from __future__ import annotations

import math
from datetime import datetime, timezone, timedelta
from typing import Any

from ...server import mcp
from ...data_facade.facade import data_facade

# ---------------------------------------------------------------------------
# Source credibility tiers — higher = more credible (0.0 – 1.0)
# ---------------------------------------------------------------------------
_SOURCE_CREDIBILITY: dict[str, float] = {
    # Tier 1 — authoritative financial news
    "reuters": 0.95, "bloomberg": 0.95, "economic times": 0.90,
    "moneycontrol": 0.88, "livemint": 0.87, "business standard": 0.87,
    "financial express": 0.85, "cnbc": 0.85, "bse": 0.92, "nse": 0.92,
    "rbi": 0.95, "sebi": 0.95,
    # Tier 2 — reputable general / business
    "ndtv": 0.78, "hindu businessline": 0.80, "times of india": 0.75,
    "india today": 0.74, "outlook": 0.72, "mint": 0.87,
    "the hindu": 0.78, "zee business": 0.70, "et markets": 0.85,
    "yahoo finance": 0.80, "investing.com": 0.75,
    # Tier 3 — aggregators / less verified
    "google news": 0.55, "gnews": 0.50, "newsapi": 0.50,
}
_DEFAULT_CREDIBILITY = 0.55

# Sentiment keywords for keyword-based enrichment
_BULLISH_KEYWORDS = frozenset({
    "upgrade", "outperform", "beat", "surge", "rally", "profit", "growth",
    "bullish", "breakout", "record high", "strong buy", "exceeds expectations",
    "dividend", "buyback", "expansion", "acquisition", "partnership",
})
_BEARISH_KEYWORDS = frozenset({
    "downgrade", "underperform", "miss", "decline", "crash", "loss",
    "bearish", "breakdown", "record low", "sell", "below expectations",
    "debt", "default", "fraud", "investigation", "layoff", "shutdown",
})


def _get_source_credibility(article: dict[str, Any]) -> float:
    """Return credibility score for an article's source."""
    source = (article.get("source") or article.get("publisher") or "").lower().strip()
    for key, score in _SOURCE_CREDIBILITY.items():
        if key in source:
            return score
    return _DEFAULT_CREDIBILITY


def _freshness_weight(article: dict[str, Any], reference_time: datetime) -> float:
    """Exponential decay: articles lose weight as they age. Half-life = 2 days."""
    pub_date = article.get("datetime") or article.get("publishedAt") or article.get("published_date")
    if not pub_date:
        return 0.5  # unknown freshness → moderate weight

    try:
        if isinstance(pub_date, (int, float)):
            pub_dt = datetime.fromtimestamp(pub_date, tz=timezone.utc)
        else:
            pub_dt = datetime.fromisoformat(str(pub_date).replace("Z", "+00:00"))
        age_hours = max((reference_time - pub_dt).total_seconds() / 3600, 0)
        half_life_hours = 48  # 2 days
        return math.exp(-0.693 * age_hours / half_life_hours)
    except (ValueError, TypeError, OSError):
        return 0.5


def _keyword_sentiment(article: dict[str, Any]) -> float:
    """Compute keyword-based sentiment from title and summary text."""
    text = (
        (article.get("headline") or article.get("title") or "")
        + " "
        + (article.get("summary") or article.get("description") or "")
    ).lower()

    bullish_hits = sum(1 for kw in _BULLISH_KEYWORDS if kw in text)
    bearish_hits = sum(1 for kw in _BEARISH_KEYWORDS if kw in text)
    total_hits = bullish_hits + bearish_hits
    if total_hits == 0:
        return 0.0
    return round((bullish_hits - bearish_hits) / total_hits, 3)


def _classify_driver(articles: list[dict[str, Any]], symbol: str) -> str:
    """Determine whether sentiment is company-specific, sector, or macro-driven."""
    sym_lower = symbol.lower()
    company_count = 0
    macro_keywords = {"rbi", "repo rate", "inflation", "gdp", "nifty", "sensex", "market"}

    for a in articles:
        text = (
            (a.get("headline") or a.get("title") or "")
            + " "
            + (a.get("summary") or a.get("description") or "")
        ).lower()
        if sym_lower in text:
            company_count += 1

    company_ratio = company_count / max(len(articles), 1)
    if company_ratio > 0.6:
        return "company_specific"
    elif company_ratio > 0.3:
        return "mixed"
    else:
        return "sector_or_macro"


def _compute_information_quality(
    articles: list[dict[str, Any]],
    source_name: str,
    reference_time: datetime,
) -> dict[str, Any]:
    """Compute an information quality score (0–100) for the dataset.

    Dimensions:
      - source_diversity: how many unique credible sources (0–30 pts)
      - freshness: average freshness weight (0–30 pts)
      - agreement: do sources agree on sentiment direction (0–25 pts)
      - volume: enough articles for statistical significance (0–15 pts)
    """
    if not articles:
        return {
            "quality_score": 0,
            "confidence_pct": 0,
            "dimensions": {
                "source_diversity": 0, "freshness": 0, "agreement": 0, "volume": 0,
            },
            "explanation": "No articles available for quality assessment.",
        }

    # Source diversity
    unique_sources: set[str] = set()
    credibilities: list[float] = []
    sentiments: list[float] = []
    freshness_vals: list[float] = []

    for a in articles:
        src = (a.get("source") or a.get("publisher") or "unknown").lower().strip()
        unique_sources.add(src)
        credibilities.append(_get_source_credibility(a))
        freshness_vals.append(_freshness_weight(a, reference_time))
        raw_sent = a.get("sentiment_score") or 0
        kw_sent = _keyword_sentiment(a)
        sentiments.append(raw_sent * 0.5 + kw_sent * 0.5)

    # Scoring dimensions
    n_sources = len(unique_sources)
    avg_cred = sum(credibilities) / len(credibilities)
    source_diversity_score = min(30, int(n_sources * 5 * avg_cred))

    avg_freshness = sum(freshness_vals) / len(freshness_vals)
    freshness_score = int(avg_freshness * 30)

    # Agreement: if most sentiments have the same sign
    pos_count = sum(1 for s in sentiments if s > 0.1)
    neg_count = sum(1 for s in sentiments if s < -0.1)
    total = len(sentiments)
    dominant = max(pos_count, neg_count)
    agreement_ratio = dominant / max(total, 1)
    agreement_score = int(agreement_ratio * 25)

    volume_score = min(15, len(articles) * 2)

    quality_score = source_diversity_score + freshness_score + agreement_score + volume_score
    quality_score = min(100, quality_score)

    return {
        "quality_score": quality_score,
        "confidence_pct": quality_score,
        "dimensions": {
            "source_diversity": source_diversity_score,
            "freshness": freshness_score,
            "agreement": agreement_score,
            "volume": volume_score,
        },
        "unique_sources": n_sources,
        "avg_source_credibility": round(avg_cred, 3),
        "explanation": (
            f"Quality {quality_score}/100 based on {n_sources} unique sources "
            f"(avg credibility {avg_cred:.0%}), freshness {avg_freshness:.0%}, "
            f"source agreement {agreement_ratio:.0%}, {len(articles)} articles."
        ),
    }


def _diversified_sentiment(
    articles: list[dict[str, Any]],
    reference_time: datetime,
) -> dict[str, Any]:
    """Compute credibility-weighted, freshness-decayed, multi-signal sentiment.

    Returns overall score (-1 to +1), per-source breakdown, and confidence.
    """
    if not articles:
        return {
            "overall_score": 0.0,
            "weighted_score": 0.0,
            "article_count": 0,
            "positive_count": 0,
            "negative_count": 0,
            "neutral_count": 0,
            "source_breakdown": [],
            "confidence": 0.0,
        }

    source_buckets: dict[str, list[dict[str, Any]]] = {}
    total_weighted = 0.0
    total_weight = 0.0
    pos = neg = neutral = 0

    for a in articles:
        src = (a.get("source") or a.get("publisher") or "unknown").lower().strip()
        cred = _get_source_credibility(a)
        fresh = _freshness_weight(a, reference_time)
        raw_sent = a.get("sentiment_score") or 0
        kw_sent = _keyword_sentiment(a)

        # Blend: 40% raw API score + 40% keyword + 20% credibility bias toward neutral
        blended = raw_sent * 0.4 + kw_sent * 0.4 + 0.0 * 0.2
        weight = cred * fresh

        total_weighted += blended * weight
        total_weight += weight

        if blended > 0.15:
            pos += 1
        elif blended < -0.15:
            neg += 1
        else:
            neutral += 1

        source_buckets.setdefault(src, []).append({
            "sentiment": round(blended, 3),
            "credibility": cred,
            "freshness": round(fresh, 3),
            "weight": round(weight, 3),
        })

    weighted_score = round(total_weighted / max(total_weight, 0.001), 3)
    # Simple score for backwards compat
    simple_score = round((pos - neg) / max(len(articles), 1), 3)

    # Per-source breakdown
    source_breakdown = []
    for src, items in sorted(source_buckets.items(), key=lambda x: -len(x[1])):
        avg_sent = sum(i["sentiment"] for i in items) / len(items)
        avg_cred = sum(i["credibility"] for i in items) / len(items)
        source_breakdown.append({
            "source": src,
            "article_count": len(items),
            "avg_sentiment": round(avg_sent, 3),
            "credibility": round(avg_cred, 3),
        })

    # Confidence: weighted by credibility and agreement
    signs = [1 if s > 0.1 else (-1 if s < -0.1 else 0)
             for s in [i["sentiment"] for items in source_buckets.values() for i in items]]
    if signs:
        dominant = max(signs.count(1), signs.count(-1), signs.count(0))
        agreement = dominant / len(signs)
    else:
        agreement = 0
    confidence = round(min(1.0, agreement * (total_weight / max(len(articles), 1))), 3)

    return {
        "overall_score": simple_score,
        "weighted_score": weighted_score,
        "article_count": len(articles),
        "positive_count": pos,
        "negative_count": neg,
        "neutral_count": neutral,
        "source_breakdown": source_breakdown,
        "confidence": confidence,
    }


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
    """Compute diversified, credibility-weighted news sentiment for a stock.

    Uses multi-dimensional scoring:
      - Source credibility weighting (Reuters/Bloomberg > aggregators)
      - Freshness decay (recent articles weighted more)
      - Keyword-based sentiment enrichment (bullish/bearish signal words)
      - Per-source sentiment breakdown
      - Information quality score (0–100)
      - Driver classification (company-specific vs sector/macro)

    Args:
        symbol: NSE/BSE ticker symbol.
        days: Look-back window in days (default 7).
    """
    now = datetime.now(timezone.utc)
    result = await data_facade.get_news(symbol, min(days, 30))
    articles = result.get("articles", result.get("data", []))
    source_name = result.get("_source", "unknown")

    sentiment = _diversified_sentiment(articles, now)
    quality = _compute_information_quality(articles, source_name, now)
    driver = _classify_driver(articles, symbol)

    return {
        "data": {
            "symbol": symbol,
            "overall_score": sentiment["overall_score"],
            "weighted_score": sentiment["weighted_score"],
            "article_count": sentiment["article_count"],
            "positive_count": sentiment["positive_count"],
            "negative_count": sentiment["negative_count"],
            "neutral_count": sentiment["neutral_count"],
            "confidence": sentiment["confidence"],
            "source_breakdown": sentiment["source_breakdown"],
            "driver_type": driver,
            "information_quality": quality,
        },
        "source": source_name,
        "cache_status": result.get("_cache", "miss"),
        "timestamp": now.isoformat(),
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
