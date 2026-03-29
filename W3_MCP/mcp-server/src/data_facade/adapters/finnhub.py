"""Finnhub adapter for company news, earnings calendar, and recommendations."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from ...config.settings import settings

logger = structlog.get_logger(__name__)

_BASE_URL = "https://finnhub.io/api/v1"


class FinnhubAdapter:
    """Fetches news, earnings calendar, and analyst recommendations from Finnhub."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=_BASE_URL,
                timeout=httpx.Timeout(15.0),
                params={"token": settings.finnhub_key},
            )
        return self._client

    async def get_company_news(
        self,
        symbol: str,
        from_date: str,
        to_date: str,
    ) -> dict[str, Any]:
        """Get company-specific news articles."""
        try:
            client = await self._get_client()
            resp = await client.get(
                "/company-news",
                params={"symbol": symbol, "from": from_date, "to": to_date},
            )
            resp.raise_for_status()
            articles = resp.json()
            return {
                "symbol": symbol,
                "articles": [
                    {
                        "headline": a.get("headline", ""),
                        "summary": a.get("summary", ""),
                        "source": a.get("source", ""),
                        "url": a.get("url", ""),
                        "datetime": a.get("datetime", 0),
                        "category": a.get("category", ""),
                    }
                    for a in (articles or [])
                ],
                "_source": "finnhub",
            }
        except Exception as exc:
            logger.error("finnhub.news.error", symbol=symbol, error=str(exc))
            return {"error": str(exc), "error_code": "FINNHUB_NEWS_FAILED", "_source": "finnhub"}

    async def get_earnings_calendar(
        self,
        from_date: str,
        to_date: str,
    ) -> dict[str, Any]:
        """Fetch upcoming earnings dates."""
        try:
            client = await self._get_client()
            resp = await client.get(
                "/calendar/earnings",
                params={"from": from_date, "to": to_date},
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "earnings": data.get("earningsCalendar", []),
                "_source": "finnhub",
            }
        except Exception as exc:
            logger.error("finnhub.earnings.error", error=str(exc))
            return {"error": str(exc), "error_code": "FINNHUB_EARNINGS_FAILED", "_source": "finnhub"}

    async def get_recommendation(self, symbol: str) -> dict[str, Any]:
        """Fetch analyst recommendation trends."""
        try:
            client = await self._get_client()
            resp = await client.get(
                "/stock/recommendation",
                params={"symbol": symbol},
            )
            resp.raise_for_status()
            return {"symbol": symbol, "recommendations": resp.json(), "_source": "finnhub"}
        except Exception as exc:
            logger.error("finnhub.recommendation.error", symbol=symbol, error=str(exc))
            return {"error": str(exc), "error_code": "FINNHUB_REC_FAILED", "_source": "finnhub"}

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
