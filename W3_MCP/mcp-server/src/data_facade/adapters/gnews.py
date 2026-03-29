"""GNews adapter for general financial news search."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from ...config.settings import settings

logger = structlog.get_logger(__name__)

_BASE_URL = "https://gnews.io/api/v4/"


class GNewsAdapter:
    """Searches news articles via the GNews API."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=_BASE_URL,
                timeout=httpx.Timeout(15.0),
            )
        return self._client

    async def search_news(
        self,
        query: str,
        max_results: int = 10,
        language: str = "en",
        country: str = "in",
    ) -> dict[str, Any]:
        """Search for news articles matching *query*."""
        try:
            client = await self._get_client()
            resp = await client.get(
                "search",
                params={
                    "q": query,
                    "lang": language,
                    "country": country,
                    "max": str(max_results),
                    "token": settings.gnews_key,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            articles = data.get("articles", [])
            return {
                "query": query,
                "total_articles": data.get("totalArticles", len(articles)),
                "articles": [
                    {
                        "title": a.get("title", ""),
                        "description": a.get("description", ""),
                        "url": a.get("url", ""),
                        "source": a.get("source", {}).get("name", ""),
                        "published_at": a.get("publishedAt", ""),
                    }
                    for a in articles
                ],
                "_source": "gnews",
            }
        except Exception as exc:
            logger.error("gnews.search.error", query=query, error=str(exc))
            return {"error": str(exc), "error_code": "GNEWS_SEARCH_FAILED", "_source": "gnews"}

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
