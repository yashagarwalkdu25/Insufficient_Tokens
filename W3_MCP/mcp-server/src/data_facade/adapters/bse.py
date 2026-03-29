"""BSE India adapter for corporate filings, results, and shareholding."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)

_BSE_BASE = "https://api.bseindia.com/BseIndiaAPI/api"
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.bseindia.com/",
    "Origin": "https://www.bseindia.com",
}


class BSEAdapter:
    """Fetch corporate announcements, quarterly results, and shareholding
    patterns from BSE India."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=_BSE_BASE,
                timeout=httpx.Timeout(20.0),
                headers=_BROWSER_HEADERS,
            )
        return self._client

    async def get_announcements(
        self,
        scrip_code: str,
        from_date: str = "",
        to_date: str = "",
    ) -> dict[str, Any]:
        """Fetch corporate announcements for a BSE scrip code."""
        try:
            client = await self._get_client()
            params: dict[str, str] = {
                "scripcode": scrip_code,
                "fromdate": from_date,
                "todate": to_date,
            }
            resp = await client.get("/AnnSubCategoryGetData/w", params=params)
            resp.raise_for_status()
            return {"scrip_code": scrip_code, "announcements": resp.json(), "_source": "bse"}
        except Exception as exc:
            logger.error("bse.announcements.error", scrip_code=scrip_code, error=str(exc))
            return {"error": str(exc), "error_code": "BSE_ANN_FAILED", "_source": "bse"}

    async def get_quarterly_results(self, scrip_code: str) -> dict[str, Any]:
        """Fetch recent quarterly financial results."""
        try:
            client = await self._get_client()
            resp = await client.get(
                "/FinancialResult/w",
                params={"scripcode": scrip_code},
            )
            resp.raise_for_status()
            return {"scrip_code": scrip_code, "results": resp.json(), "_source": "bse"}
        except Exception as exc:
            logger.error("bse.results.error", scrip_code=scrip_code, error=str(exc))
            return {"error": str(exc), "error_code": "BSE_RESULTS_FAILED", "_source": "bse"}

    async def get_shareholding(self, scrip_code: str) -> dict[str, Any]:
        """Fetch shareholding pattern data."""
        try:
            client = await self._get_client()
            resp = await client.get(
                "/ShareholdingPattern/w",
                params={"scripcode": scrip_code},
            )
            resp.raise_for_status()
            return {"scrip_code": scrip_code, "shareholding": resp.json(), "_source": "bse"}
        except Exception as exc:
            logger.error("bse.shareholding.error", scrip_code=scrip_code, error=str(exc))
            return {"error": str(exc), "error_code": "BSE_SH_FAILED", "_source": "bse"}

    async def get_corporate_actions(self, scrip_code: str) -> dict[str, Any]:
        """Fetch upcoming and recent corporate actions (dividends, splits, etc.)."""
        try:
            client = await self._get_client()
            resp = await client.get(
                "/CorporateAction/w",
                params={"scripcode": scrip_code},
            )
            resp.raise_for_status()
            return {"scrip_code": scrip_code, "actions": resp.json(), "_source": "bse"}
        except Exception as exc:
            logger.error("bse.corp_actions.error", scrip_code=scrip_code, error=str(exc))
            return {"error": str(exc), "error_code": "BSE_CA_FAILED", "_source": "bse"}

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
