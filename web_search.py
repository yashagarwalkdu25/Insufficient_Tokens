"""Web search module using DuckDuckGo (no API key required)."""
from __future__ import annotations
import logging
import time
from duckduckgo_search import DDGS
from config import MAX_SEARCH_RESULTS, TRUSTED_DOMAINS

logger = logging.getLogger(__name__)

# Browser-like headers to avoid DDG rate-limiting the default library user-agent
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}
_MAX_RETRIES = 3
_RETRY_DELAYS = [2, 5, 10]  # seconds — exponential backoff


def search_web(query: str, max_results: int = MAX_SEARCH_RESULTS) -> list[dict]:
    """Search the web for evidence. Returns list of {title, snippet, url}."""
    for attempt in range(_MAX_RETRIES + 1):
        try:
            ddgs = DDGS(headers=_HEADERS)
            raw = ddgs.text(query, max_results=max_results)
            results = []
            for r in raw:
                results.append({
                    "title": r.get("title", ""),
                    "snippet": r.get("body", ""),
                    "url": r.get("href", ""),
                })
            return results
        except Exception as e:
            if "Ratelimit" in str(e) and attempt < _MAX_RETRIES:
                delay = _RETRY_DELAYS[min(attempt, len(_RETRY_DELAYS) - 1)]
                logger.info("DDG rate-limited, retrying in %ds (attempt %d/%d)…",
                            delay, attempt + 1, _MAX_RETRIES)
                time.sleep(delay)
                continue
            logger.warning("Web search failed for query '%s': %s", query, e)
            return []
    return []


def search_trusted(query: str, max_results: int = MAX_SEARCH_RESULTS) -> list[dict]:
    """Search only trusted news domains for higher-quality evidence."""
    # Use fewer site filters to keep query short and avoid DDG issues
    domain_filter = " OR ".join(f"site:{d}" for d in TRUSTED_DOMAINS[:4])
    full_query = f"{query} ({domain_filter})"
    return search_web(full_query, max_results)


def search_fact_checkers(claim: str) -> list[dict]:
    """Search fact-checking sites specifically."""
    fc_domains = "site:snopes.com OR site:factcheck.org OR site:politifact.com"
    return search_web(f"{claim} ({fc_domains})", max_results=5)
