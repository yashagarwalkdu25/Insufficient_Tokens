"""Web search module using DuckDuckGo with Tavily fallback."""
from __future__ import annotations
import logging
import time
from urllib.parse import urlparse
from duckduckgo_search import DDGS
from config import MAX_SEARCH_RESULTS, TRUSTED_DOMAINS, TAVILY_API_KEY

logger = logging.getLogger(__name__)

_MAX_RETRIES = 1
_RETRY_DELAYS = [2]  # minimal retry since Tavily fallback is fast


def _extract_domain(url: str) -> str:
    """Extract domain from URL, stripping www. prefix."""
    try:
        domain = urlparse(url).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


# ── Tavily fallback ──────────────────────────────────────────────────

def _tavily_search(query: str, max_results: int = MAX_SEARCH_RESULTS,
                   include_domains: list[str] | None = None) -> list[dict]:
    """Search using Tavily API (fallback when DDG is rate-limited).

    Requires TAVILY_API_KEY environment variable.
    Free tier: 1000 queries/month at https://tavily.com
    """
    if not TAVILY_API_KEY:
        logger.warning("Tavily API key not set — cannot use fallback search. "
                       "Set TAVILY_API_KEY in .env")
        return []

    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=TAVILY_API_KEY)

        kwargs = {
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
        }
        if include_domains:
            kwargs["include_domains"] = include_domains

        response = client.search(**kwargs)
        results = []
        for r in response.get("results", []):
            results.append({
                "title": r.get("title", ""),
                "snippet": r.get("content", ""),
                "url": r.get("url", ""),
            })
        logger.info("Tavily search returned %d results for '%s'",
                    len(results), query[:60])
        return results

    except Exception as e:
        logger.warning("Tavily search failed for '%s': %s", query[:60], e)
        return []


# ── DuckDuckGo primary search ────────────────────────────────────────

def _ddg_search(query: str, max_results: int = MAX_SEARCH_RESULTS) -> list[dict]:
    """Search using DuckDuckGo with retries. Returns [] on failure."""
    for attempt in range(_MAX_RETRIES + 1):
        try:
            ddgs = DDGS()
            raw = ddgs.text(query, max_results=max_results)
            results = []
            for r in raw:
                results.append({
                    "title": r.get("title", ""),
                    "snippet": r.get("body", ""),
                    "url": r.get("href", ""),
                })
            logger.info("DDG search returned %d results for '%s'",
                        len(results), query[:60])
            return results
        except Exception as e:
            if "Ratelimit" in str(e) and attempt < _MAX_RETRIES:
                delay = _RETRY_DELAYS[min(attempt, len(_RETRY_DELAYS) - 1)]
                logger.warning("DDG rate-limited, retrying in %ds (attempt %d/%d)…",
                               delay, attempt + 1, _MAX_RETRIES)
                time.sleep(delay)
                continue
            logger.warning("DDG search failed for '%s': %s", query[:60], e)
            return []
    return []


# ── Public API (DDG first, Tavily fallback) ──────────────────────────

def search_web(query: str, max_results: int = MAX_SEARCH_RESULTS) -> list[dict]:
    """Search the web for evidence. Returns list of {title, snippet, url}.

    Tries DuckDuckGo first, falls back to Tavily if DDG fails.
    """
    results = _ddg_search(query, max_results=max_results)
    if results:
        return results

    logger.info("DDG failed — falling back to Tavily for '%s'", query[:60])
    return _tavily_search(query, max_results=max_results)


def search_trusted(query: str, max_results: int = MAX_SEARCH_RESULTS) -> list[dict]:
    """Search for evidence, prioritising trusted news sources.

    Tries DDG first with news keywords, falls back to Tavily with domain filtering.
    """
    # Try DDG with news-oriented keywords
    full_query = f"{query} news Reuters AP BBC"
    results = _ddg_search(full_query, max_results=max_results * 2)

    if results:
        # Prefer results from trusted domains
        trusted = [r for r in results
                   if _extract_domain(r.get("url", "")) in TRUSTED_DOMAINS]
        if trusted:
            return trusted[:max_results]
        return results[:max_results]

    # Fallback: Tavily with trusted domain filtering
    logger.info("DDG failed — falling back to Tavily trusted search for '%s'",
                query[:60])
    tavily_results = _tavily_search(
        query, max_results=max_results,
        include_domains=TRUSTED_DOMAINS[:10],  # Tavily limits domain count
    )
    if tavily_results:
        return tavily_results

    # Last resort: Tavily without domain filter
    return _tavily_search(query, max_results=max_results)


def search_fact_checkers(claim: str) -> list[dict]:
    """Search fact-checking sites for the claim.

    Tries DDG first, falls back to Tavily with fact-checker domains.
    """
    fc_domains = ["snopes.com", "factcheck.org", "politifact.com", "fullfact.org"]

    # Try DDG with fact-check keywords
    full_query = f"{claim} fact check Snopes PolitiFact FactCheck.org"
    results = _ddg_search(full_query, max_results=8)

    if results:
        fc_results = [r for r in results
                      if _extract_domain(r.get("url", "")) in fc_domains]
        if fc_results:
            return fc_results[:5]
        return results[:5]

    # Fallback: Tavily targeting fact-checker domains
    logger.info("DDG failed — falling back to Tavily fact-check search for '%s'",
                claim[:60])
    tavily_results = _tavily_search(
        f"{claim} fact check",
        max_results=5,
        include_domains=fc_domains,
    )
    if tavily_results:
        return tavily_results

    # Last resort: Tavily general fact-check search
    return _tavily_search(f"{claim} fact check", max_results=5)
