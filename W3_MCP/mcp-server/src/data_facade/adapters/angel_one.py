"""Angel One SmartAPI adapter for live market data."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
import structlog

from ...config.settings import settings

logger = structlog.get_logger(__name__)

_SMART_API_BASE = "https://apiconnect.angelbroking.com"


class AngelOneAdapter:
    """Fetches live quotes and historical OHLCV via Angel One SmartAPI.

    Credentials: ``ANGEL_ONE_API_KEY`` (X-PrivateKey), ``ANGEL_ONE_API_SECRET`` (app secret from dashboard),
    plus client code / password / TOTP for session login. See https://smartapi.angelone.in/docs
    """

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._jwt_token: str = ""
        self._refresh_token: str = ""
        self._feed_token: str = ""

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=_SMART_API_BASE,
                timeout=httpx.Timeout(15.0),
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "X-UserType": "USER",
                    "X-SourceID": "WEB",
                    "X-PrivateKey": settings.angel_one_api_key,
                },
            )
        return self._client

    async def login(self) -> dict[str, Any]:
        """Authenticate with Angel One using TOTP and return session tokens."""
        try:
            from pyotp import TOTP

            totp = TOTP(settings.angel_one_totp_secret).now()
            client = await self._get_client()
            resp = await client.post(
                "/rest/auth/angelbroking/user/v1/loginByPassword",
                json={
                    "clientcode": settings.angel_one_client_code,
                    "password": settings.angel_one_password,
                    "totp": totp,
                },
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            self._jwt_token = data.get("jwtToken", "")
            self._refresh_token = data.get("refreshToken", "")
            self._feed_token = data.get("feedToken", "")
            logger.info("angel_one.login.success")
            return {"status": "ok"}
        except Exception as exc:
            logger.error("angel_one.login.failed", error=str(exc))
            return {"error": str(exc), "error_code": "ANGEL_LOGIN_FAILED"}

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._jwt_token}"}

    async def get_quote(self, symbol: str) -> dict[str, Any]:
        """Fetch real-time quote for a symbol, returning normalized dict."""
        try:
            client = await self._get_client()
            resp = await client.post(
                "/rest/secure/angelbroking/market/v1/quote/",
                headers=self._auth_headers(),
                json={
                    "mode": "FULL",
                    "exchangeTokens": {"NSE": [symbol]},
                },
            )
            resp.raise_for_status()
            result = resp.json()
            fetched = result.get("data", {}).get("fetched", [{}])
            q = fetched[0] if fetched else {}
            return {
                "symbol": symbol,
                "ltp": q.get("ltp", 0.0),
                "change": q.get("netChange", 0.0),
                "change_pct": q.get("percentChange", 0.0),
                "open": q.get("open", 0.0),
                "high": q.get("high", 0.0),
                "low": q.get("low", 0.0),
                "close": q.get("close", 0.0),
                "volume": q.get("tradeVolume", 0),
                "exchange": "NSE",
                "_source": "angel_one",
            }
        except Exception as exc:
            logger.error("angel_one.get_quote.error", symbol=symbol, error=str(exc))
            return {"error": str(exc), "error_code": "ANGEL_QUOTE_FAILED", "_source": "angel_one"}

    async def get_historical(
        self,
        symbol: str,
        from_date: str,
        to_date: str,
        interval: str = "ONE_DAY",
    ) -> dict[str, Any]:
        """Fetch historical candles. *interval*: ONE_MINUTE, FIVE_MINUTE, ONE_DAY, etc."""
        try:
            client = await self._get_client()
            resp = await client.post(
                "/rest/secure/angelbroking/historical/v1/getCandleData",
                headers=self._auth_headers(),
                json={
                    "exchange": "NSE",
                    "symboltoken": symbol,
                    "interval": interval,
                    "fromdate": from_date,
                    "todate": to_date,
                },
            )
            resp.raise_for_status()
            candles = resp.json().get("data", []) or []
            bars = [
                {
                    "date": c[0],
                    "open": c[1],
                    "high": c[2],
                    "low": c[3],
                    "close": c[4],
                    "volume": c[5],
                }
                for c in candles
            ]
            return {"symbol": symbol, "interval": interval, "bars": bars, "_source": "angel_one"}
        except Exception as exc:
            logger.error("angel_one.get_historical.error", symbol=symbol, error=str(exc))
            return {"error": str(exc), "error_code": "ANGEL_HISTORICAL_FAILED", "_source": "angel_one"}

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
