"""Web search module using DuckDuckGo (no API key required)."""
from __future__ import annotations
import logging
from duckduckgo_search import DDGS
from config import MAX_SEARCH_RESULTS, TRUSTED_DOMAINS

logger = logging.getLogger(__name__)


def search_web(query: str, max_results: int = MAX_SEARCH_RESULTS) -> list[dict]:
    """Search the web for evidence. Returns list of {title, snippet, url}."""
    try:
        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=max_results))
        results = []
        for r in raw:
            results.append({
                "title": r.get("title", ""),
                "snippet": r.get("body", ""),
                "url": r.get("href", ""),
            })
        return results
    except Exception as e:
        logger.warning("Web search failed: %s", e)
        return []


def search_trusted(query: str, max_results: int = MAX_SEARCH_RESULTS) -> list[dict]:
    """Search only trusted news domains for higher-quality evidence."""
    domain_filter = " OR ".join(f"site:{d}" for d in TRUSTED_DOMAINS[:6])
    full_query = f"{query} ({domain_filter})"
    return search_web(full_query, max_results)


def search_fact_checkers(claim: str) -> list[dict]:
    """Search fact-checking sites specifically."""
    fc_domains = "site:snopes.com OR site:factcheck.org OR site:politifact.com"
    return search_web(f"{claim} ({fc_domains})", max_results=5)
