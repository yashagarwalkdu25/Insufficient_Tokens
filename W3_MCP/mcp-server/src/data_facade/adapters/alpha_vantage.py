"""Alpha Vantage adapter for technicals and fundamental statements."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from ...config.settings import settings

logger = structlog.get_logger(__name__)

_BASE_URL = "https://www.alphavantage.co/query"


def _safe_av_float(value: Any) -> float | None:
    """Convert Alpha Vantage string values to float, returning None for missing/invalid."""
    if value is None or value == "None" or value == "-":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


class AlphaVantageAdapter:
    """Fetches technical indicators, income statements, balance sheets,
    and company overviews from Alpha Vantage.

    Uses BSE ticker suffix (e.g. ``RELIANCE.BSE``) for Indian stocks.
    """

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(20.0),
            )
        return self._client

    def _params(self, **extra: str) -> dict[str, str]:
        return {"apikey": settings.alpha_vantage_key, **extra}

    async def get_technical_indicator(
        self,
        symbol: str,
        indicator: str = "RSI",
        interval: str = "daily",
    ) -> dict[str, Any]:
        """Fetch a technical indicator (RSI, SMA, EMA, MACD, etc.)."""
        try:
            client = await self._get_client()
            resp = await client.get(
                _BASE_URL,
                params=self._params(
                    function=indicator,
                    symbol=symbol,
                    interval=interval,
                    time_period="14",
                    series_type="close",
                ),
            )
            resp.raise_for_status()
            data = resp.json()
            meta_key = [k for k in data if "Meta" in k]
            data_key = [k for k in data if "Technical" in k or "Analysis" in k]
            values: dict[str, Any] = {}
            if data_key:
                raw = data[data_key[0]]
                latest_date = next(iter(raw), None)
                if latest_date:
                    values = raw[latest_date]
            return {
                "symbol": symbol,
                "indicator": indicator,
                "interval": interval,
                "values": values,
                "_source": "alpha_vantage",
            }
        except Exception as exc:
            logger.error("alpha_vantage.indicator.error", symbol=symbol, error=str(exc))
            return {"error": str(exc), "error_code": "AV_INDICATOR_FAILED", "_source": "alpha_vantage"}

    async def get_income_statement(self, symbol: str) -> dict[str, Any]:
        """Fetch annual & quarterly income statements."""
        try:
            client = await self._get_client()
            resp = await client.get(
                _BASE_URL,
                params=self._params(function="INCOME_STATEMENT", symbol=symbol),
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "symbol": symbol,
                "annual": data.get("annualReports", []),
                "quarterly": data.get("quarterlyReports", []),
                "_source": "alpha_vantage",
            }
        except Exception as exc:
            logger.error("alpha_vantage.income.error", symbol=symbol, error=str(exc))
            return {"error": str(exc), "error_code": "AV_INCOME_FAILED", "_source": "alpha_vantage"}

    async def get_balance_sheet(self, symbol: str) -> dict[str, Any]:
        """Fetch annual & quarterly balance sheets."""
        try:
            client = await self._get_client()
            resp = await client.get(
                _BASE_URL,
                params=self._params(function="BALANCE_SHEET", symbol=symbol),
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "symbol": symbol,
                "annual": data.get("annualReports", []),
                "quarterly": data.get("quarterlyReports", []),
                "_source": "alpha_vantage",
            }
        except Exception as exc:
            logger.error("alpha_vantage.balance.error", symbol=symbol, error=str(exc))
            return {"error": str(exc), "error_code": "AV_BALANCE_FAILED", "_source": "alpha_vantage"}

    async def get_overview(self, symbol: str) -> dict[str, Any]:
        """Fetch company overview (sector, market cap, P/E, etc.)."""
        try:
            client = await self._get_client()
            resp = await client.get(
                _BASE_URL,
                params=self._params(function="OVERVIEW", symbol=symbol),
            )
            resp.raise_for_status()
            data = resp.json()
            # Treat empty or error responses as failure so fallback chain continues
            if not data or "Symbol" not in data:
                logger.warning("alpha_vantage.overview.empty", symbol=symbol)
                return {"error": "Empty overview response", "error_code": "AV_OVERVIEW_EMPTY", "_source": "alpha_vantage"}
            return {
                "symbol": symbol,
                "pe_ratio": _safe_av_float(data.get("TrailingPE")),
                "pb_ratio": _safe_av_float(data.get("PriceToBookRatio")),
                "roe": _safe_av_float(data.get("ReturnOnEquityTTM")),
                "roce": None,
                "debt_to_equity": None,
                "current_ratio": None,
                "dividend_yield": _safe_av_float(data.get("DividendYield")),
                "ev_to_ebitda": _safe_av_float(data.get("EVToEBITDA")),
                "price_to_sales": _safe_av_float(data.get("PriceToSalesRatioTTM")),
                "eps": _safe_av_float(data.get("EPS")),
                "sector_avg_pe": None,
                "sector": data.get("Sector"),
                "industry": data.get("Industry"),
                "market_cap": _safe_av_float(data.get("MarketCapitalization")),
                "_source": "alpha_vantage",
            }
        except Exception as exc:
            logger.error("alpha_vantage.overview.error", symbol=symbol, error=str(exc))
            return {"error": str(exc), "error_code": "AV_OVERVIEW_FAILED", "_source": "alpha_vantage"}

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
