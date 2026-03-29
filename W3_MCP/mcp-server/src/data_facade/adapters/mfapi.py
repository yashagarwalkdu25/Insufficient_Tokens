"""MFapi.in adapter for mutual-fund NAV data (no auth required)."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)

_BASE_URL = "https://api.mfapi.in/mf/"


class MFApiAdapter:
    """Read-only adapter for the open MFapi.in mutual-fund API."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=_BASE_URL,
                timeout=httpx.Timeout(15.0),
            )
        return self._client

    async def search_schemes(self, query: str) -> dict[str, Any]:
        """Search mutual-fund schemes by name/keyword."""
        try:
            client = await self._get_client()
            resp = await client.get("search", params={"q": query})
            resp.raise_for_status()
            results = resp.json()
            return {"schemes": results, "_source": "mfapi"}
        except Exception as exc:
            logger.error("mfapi.search.error", query=query, error=str(exc))
            return {"error": str(exc), "error_code": "MFAPI_SEARCH_FAILED", "_source": "mfapi"}

    async def get_nav(self, scheme_code: str) -> dict[str, Any]:
        """Get the latest NAV for a mutual-fund scheme."""
        try:
            client = await self._get_client()
            resp = await client.get(f"{scheme_code}/latest")
            resp.raise_for_status()
            data = resp.json()
            meta = data.get("meta", {})
            nav_data = data.get("data", [{}])
            latest = nav_data[0] if nav_data else {}
            return {
                "scheme_code": scheme_code,
                "scheme_name": meta.get("scheme_name", ""),
                "fund_house": meta.get("fund_house", ""),
                "scheme_type": meta.get("scheme_type", ""),
                "nav": latest.get("nav", ""),
                "date": latest.get("date", ""),
                "_source": "mfapi",
            }
        except Exception as exc:
            logger.error("mfapi.nav.error", scheme_code=scheme_code, error=str(exc))
            return {"error": str(exc), "error_code": "MFAPI_NAV_FAILED", "_source": "mfapi"}

    async def get_nav_history(self, scheme_code: str) -> dict[str, Any]:
        """Get full historical NAV series for a scheme."""
        try:
            client = await self._get_client()
            resp = await client.get(str(scheme_code))
            resp.raise_for_status()
            data = resp.json()
            meta = data.get("meta", {})
            return {
                "scheme_code": scheme_code,
                "scheme_name": meta.get("scheme_name", ""),
                "data": data.get("data", []),
                "_source": "mfapi",
            }
        except Exception as exc:
            logger.error("mfapi.history.error", scheme_code=scheme_code, error=str(exc))
            return {"error": str(exc), "error_code": "MFAPI_HISTORY_FAILED", "_source": "mfapi"}

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
