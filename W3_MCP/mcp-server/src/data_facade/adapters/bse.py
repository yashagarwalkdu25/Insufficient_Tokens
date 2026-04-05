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
        self._scrip_cache: dict[str, str] = {}

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=_BSE_BASE,
                timeout=httpx.Timeout(20.0),
                headers=_BROWSER_HEADERS,
            )
        return self._client

    async def search_scrip(self, symbol: str) -> str | None:
        """Dynamically look up a BSE scrip code from a symbol/company name
        using BSE's suggest API. Returns the numeric scrip code or None."""
        if symbol in self._scrip_cache:
            return self._scrip_cache[symbol]

        if symbol.isdigit():
            return symbol

        try:
            client = await self._get_client()
            resp = await client.get(
                "/Suggest/w",
                params={"Group": "EQ", "Ession": "1", "Type": "S", "Text": symbol},
            )
            resp.raise_for_status()
            suggestions = resp.json()
            if not suggestions:
                return None
            sym_upper = symbol.upper()
            for item in suggestions:
                parts = str(item).split("/")
                if len(parts) >= 2:
                    scrip_code = parts[0].strip()
                    scrip_name = parts[1].strip().upper()
                    if sym_upper in scrip_name or scrip_name in sym_upper:
                        self._scrip_cache[symbol] = scrip_code
                        logger.info("bse.scrip_resolved", symbol=symbol, scrip_code=scrip_code)
                        return scrip_code
            first = str(suggestions[0]).split("/")[0].strip()
            if first.isdigit():
                self._scrip_cache[symbol] = first
                return first
            return None
        except Exception as exc:
            logger.warning("bse.scrip_search.error", symbol=symbol, error=str(exc))
            return None

    async def _resolve_scrip(self, scrip_or_symbol: str) -> str | None:
        """Resolve to a valid numeric BSE scrip code."""
        if scrip_or_symbol.isdigit():
            return scrip_or_symbol
        return await self.search_scrip(scrip_or_symbol)

    async def get_announcements(
        self,
        scrip_code: str,
        from_date: str = "",
        to_date: str = "",
    ) -> dict[str, Any]:
        """Fetch corporate announcements for a BSE scrip code."""
        resolved = await self._resolve_scrip(scrip_code)
        if not resolved:
            return {"error": f"Cannot resolve BSE scrip for '{scrip_code}'", "error_code": "BSE_SCRIP_NOT_FOUND", "_source": "bse"}
        try:
            client = await self._get_client()
            params: dict[str, str] = {
                "scripcode": resolved,
                "fromdate": from_date,
                "todate": to_date,
            }
            resp = await client.get("/AnnSubCategoryGetData/w", params=params)
            resp.raise_for_status()
            return {"scrip_code": resolved, "announcements": resp.json(), "_source": "bse"}
        except Exception as exc:
            logger.error("bse.announcements.error", scrip_code=resolved, error=str(exc))
            return {"error": str(exc), "error_code": "BSE_ANN_FAILED", "_source": "bse"}

    async def get_quarterly_results(self, scrip_code: str) -> dict[str, Any]:
        """Fetch recent quarterly financial results."""
        resolved = await self._resolve_scrip(scrip_code)
        if not resolved:
            return {"error": f"Cannot resolve BSE scrip for '{scrip_code}'", "error_code": "BSE_SCRIP_NOT_FOUND", "_source": "bse"}
        try:
            client = await self._get_client()
            resp = await client.get(
                "/FinancialResult/w",
                params={"scripcode": resolved},
            )
            resp.raise_for_status()
            return {"scrip_code": resolved, "results": resp.json(), "_source": "bse"}
        except Exception as exc:
            logger.error("bse.results.error", scrip_code=resolved, error=str(exc))
            return {"error": str(exc), "error_code": "BSE_RESULTS_FAILED", "_source": "bse"}

    async def get_shareholding(self, scrip_code: str) -> dict[str, Any]:
        """Fetch shareholding pattern data and normalize into standard format."""
        resolved = await self._resolve_scrip(scrip_code)
        if not resolved:
            return {"error": f"Cannot resolve BSE scrip for '{scrip_code}'", "error_code": "BSE_SCRIP_NOT_FOUND", "_source": "bse"}
        try:
            client = await self._get_client()
            resp = await client.get(
                "/ShareholdingPattern/w",
                params={"scripcode": resolved},
            )
            resp.raise_for_status()
            raw = resp.json()

            entries = self._parse_shareholding(raw)
            if not entries:
                return {"error": "BSE returned empty shareholding", "error_code": "BSE_SH_EMPTY", "_source": "bse"}

            return {"scrip_code": resolved, "entries": entries, "_source": "bse"}
        except Exception as exc:
            logger.error("bse.shareholding.error", scrip_code=resolved, error=str(exc))
            return {"error": str(exc), "error_code": "BSE_SH_FAILED", "_source": "bse"}

    @staticmethod
    def _parse_shareholding(raw: Any) -> list[dict[str, Any]]:
        """Parse BSE shareholding JSON into normalized entries."""
        entries: list[dict[str, Any]] = []
        if not raw:
            return entries

        items = raw if isinstance(raw, list) else [raw]
        for item in items:
            if not isinstance(item, dict):
                continue

            def _pct(key: str) -> float | None:
                val = item.get(key)
                if val is None:
                    return None
                try:
                    return round(float(val), 2)
                except (ValueError, TypeError):
                    return None

            promoter = (
                _pct("SHPPromoters")
                or _pct("promoterHolding")
                or _pct("Promoter_Holding")
            )
            fii = (
                _pct("SHPForeignInstitution")
                or _pct("fiiHolding")
                or _pct("FII_Holding")
            )
            dii = (
                _pct("SHPDomesticInstitution")
                or _pct("diiHolding")
                or _pct("DII_Holding")
            )
            public = (
                _pct("SHPPublic")
                or _pct("publicHolding")
                or _pct("Public_Holding")
            )
            quarter = item.get("SHPDate") or item.get("quarter") or "latest"

            if promoter is not None or fii is not None:
                entries.append({
                    "quarter": quarter,
                    "promoter": promoter,
                    "fii": fii,
                    "dii": dii,
                    "retail": public,
                })
        return entries

    async def get_board_meetings(
        self,
        from_date: str = "",
        to_date: str = "",
    ) -> dict[str, Any]:
        """Fetch upcoming board meetings (earnings dates) from BSE.

        BSE's board meetings API lists companies whose boards are meeting
        to consider quarterly results — this is the primary source for
        Indian earnings calendar data.
        """
        try:
            client = await self._get_client()
            params: dict[str, str] = {}
            if from_date:
                params["fromdate"] = from_date
            if to_date:
                params["todate"] = to_date
            resp = await client.get(
                "/BordMeetGetData/w",
                params=params,
            )
            resp.raise_for_status()
            raw = resp.json()
            meetings = raw if isinstance(raw, list) else raw.get("Table", raw.get("data", []))

            entries: list[dict[str, Any]] = []
            for item in meetings:
                if not isinstance(item, dict):
                    continue
                purpose = (item.get("PURPOSE") or item.get("purpose") or "").lower()
                if "result" not in purpose and "financial" not in purpose and "dividend" not in purpose:
                    continue

                scrip_code = item.get("SCRIP_CD") or item.get("scripcode") or ""
                company_name = item.get("SLONGNAME") or item.get("company_name") or ""
                symbol = item.get("NSURL") or item.get("symbol") or ""
                if symbol and "symbol=" in symbol:
                    symbol = symbol.split("symbol=")[-1].split("&")[0]
                meeting_date = item.get("BOARD_MEETING_DATE") or item.get("meeting_date") or ""
                if meeting_date and "T" in meeting_date:
                    meeting_date = meeting_date.split("T")[0]

                entries.append({
                    "symbol": symbol.upper() if symbol else "",
                    "company_name": company_name,
                    "scrip_code": str(scrip_code),
                    "date": meeting_date,
                    "purpose": item.get("PURPOSE") or item.get("purpose") or "",
                    "exchange": "BSE",
                })

            return {
                "earnings": entries,
                "total_count": len(entries),
                "_source": "bse",
            }
        except Exception as exc:
            logger.error("bse.board_meetings.error", error=str(exc))
            return {"error": str(exc), "error_code": "BSE_BM_FAILED", "_source": "bse"}

    async def get_corporate_actions(self, scrip_code: str) -> dict[str, Any]:
        """Fetch upcoming and recent corporate actions (dividends, splits, etc.)."""
        resolved = await self._resolve_scrip(scrip_code)
        if not resolved:
            return {"error": f"Cannot resolve BSE scrip for '{scrip_code}'", "error_code": "BSE_SCRIP_NOT_FOUND", "_source": "bse"}
        try:
            client = await self._get_client()
            resp = await client.get(
                "/CorporateAction/w",
                params={"scripcode": resolved},
            )
            resp.raise_for_status()
            return {"scrip_code": resolved, "actions": resp.json(), "_source": "bse"}
        except Exception as exc:
            logger.error("bse.corp_actions.error", scrip_code=resolved, error=str(exc))
            return {"error": str(exc), "error_code": "BSE_CA_FAILED", "_source": "bse"}

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
