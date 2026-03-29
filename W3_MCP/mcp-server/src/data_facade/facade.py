"""DataFacade — unified entry-point for all upstream data with
fallback chains, circuit breakers, and dual-layer caching."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

import structlog

from ..config.constants import (
    FALLBACK_CHAIN_FILINGS,
    FALLBACK_CHAIN_FUNDAMENTALS,
    FALLBACK_CHAIN_MACRO,
    FALLBACK_CHAIN_MF,
    FALLBACK_CHAIN_NEWS,
    FALLBACK_CHAIN_PRICE,
    TTL_EARNINGS,
    TTL_FILINGS,
    TTL_FUNDAMENTALS,
    TTL_MACRO,
    TTL_MF_NAV,
    TTL_NEWS,
    TTL_QUOTE_MARKET_HOURS,
    TTL_SHAREHOLDING,
    TTL_TECHNICAL_INDICATORS,
)
from .cache import dual_cache
from .circuit_breaker import CircuitBreaker, CircuitOpenError
from .isin_mapper import isin_mapper
from .adapters.angel_one import AngelOneAdapter
from .adapters.alpha_vantage import AlphaVantageAdapter
from .adapters.bse import BSEAdapter
from .adapters.finnhub import FinnhubAdapter
from .adapters.gnews import GNewsAdapter
from .adapters.mfapi import MFApiAdapter
from .adapters.rbi_dbie import RBIDBIEAdapter
from .adapters.yfinance_adapter import YFinanceAdapter

logger = structlog.get_logger(__name__)


class DataFacade:
    """Singleton facade that routes every data request through:

        L1 cache → L2 cache → source₁ → source₂ → stale cache → ErrorResponse

    Each source call is wrapped in a per-source circuit breaker.
    """

    def __init__(self) -> None:
        self.angel = AngelOneAdapter()
        self.alpha = AlphaVantageAdapter()
        self.bse = BSEAdapter()
        self.finnhub = FinnhubAdapter()
        self.gnews = GNewsAdapter()
        self.mfapi = MFApiAdapter()
        self.rbi = RBIDBIEAdapter()
        self.yfinance = YFinanceAdapter()

        self._breakers: dict[str, CircuitBreaker] = {
            "angel_one": CircuitBreaker("angel_one"),
            "yfinance": CircuitBreaker("yfinance"),
            "alpha_vantage": CircuitBreaker("alpha_vantage"),
            "finnhub": CircuitBreaker("finnhub"),
            "gnews": CircuitBreaker("gnews"),
            "mfapi": CircuitBreaker("mfapi"),
            "bse": CircuitBreaker("bse"),
            "rbi_dbie": CircuitBreaker("rbi_dbie"),
        }

        self._source_map: dict[str, Any] = {
            "angel_one": self.angel,
            "yfinance": self.yfinance,
            "alpha_vantage": self.alpha,
            "finnhub": self.finnhub,
            "gnews": self.gnews,
            "mfapi": self.mfapi,
            "bse": self.bse,
            "rbi_dbie": self.rbi,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _call_source(
        self,
        source_name: str,
        coro_factory: Any,
    ) -> dict[str, Any] | None:
        """Invoke *coro_factory* inside the source's circuit breaker."""
        breaker = self._breakers[source_name]
        try:
            async with breaker:
                result = await coro_factory()
                if "error" in result:
                    breaker.record_failure()
                    return None
                return result
        except CircuitOpenError:
            logger.info("facade.circuit_open", source=source_name)
            return None
        except Exception as exc:
            logger.error("facade.source_error", source=source_name, error=str(exc))
            return None

    async def _fallback_chain(
        self,
        data_type: str,
        identifier: str,
        ttl: int,
        chain: list[str],
        call_map: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute the standard L1→L2→sources→stale→error pipeline."""
        cached = await dual_cache.get(data_type, identifier)
        if cached is not None:
            cached["_cache"] = "hit"
            cached["_stale"] = False
            return cached

        for source_name in chain:
            factory = call_map.get(source_name)
            if factory is None:
                continue
            result = await self._call_source(source_name, factory)
            if result is not None:
                result["_cache"] = "miss"
                result["_stale"] = False
                result.setdefault("_source", source_name)
                await dual_cache.set(data_type, identifier, result, ttl)
                return result

        stale = await dual_cache.get_stale(data_type, identifier)
        if stale is not None:
            stale["_cache"] = "stale"
            stale["_stale"] = True
            logger.info("facade.serving_stale", data_type=data_type, id=identifier)
            return stale

        return {
            "error": f"All sources failed for {data_type}:{identifier}",
            "error_code": "ALL_SOURCES_FAILED",
            "_source": "none",
            "_cache": "miss",
            "_stale": False,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_price(self, symbol: str) -> dict[str, Any]:
        mapping = isin_mapper.resolve(symbol)
        nse = mapping.nse_symbol if mapping else symbol

        return await self._fallback_chain(
            data_type="price",
            identifier=nse,
            ttl=TTL_QUOTE_MARKET_HOURS,
            chain=FALLBACK_CHAIN_PRICE,
            call_map={
                "angel_one": lambda: self.angel.get_quote(nse),
                "yfinance": lambda: self.yfinance.get_quote(nse),
            },
        )

    async def get_fundamentals(self, symbol: str) -> dict[str, Any]:
        mapping = isin_mapper.resolve(symbol)
        av_ticker = mapping.alpha_vantage_ticker if mapping else f"{symbol}.BSE"

        return await self._fallback_chain(
            data_type="fundamentals",
            identifier=symbol,
            ttl=TTL_FUNDAMENTALS,
            chain=FALLBACK_CHAIN_FUNDAMENTALS,
            call_map={
                "alpha_vantage": lambda: self.alpha.get_overview(av_ticker),
                "yfinance": lambda: self.yfinance.get_overview(symbol),
            },
        )

    async def get_news(self, symbol: str, days: int = 7) -> dict[str, Any]:
        to_date = datetime.utcnow().strftime("%Y-%m-%d")
        from_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

        return await self._fallback_chain(
            data_type="news",
            identifier=f"{symbol}:{days}d",
            ttl=TTL_NEWS,
            chain=FALLBACK_CHAIN_NEWS,
            call_map={
                "finnhub": lambda: self.finnhub.get_company_news(symbol, from_date, to_date),
                "gnews": lambda: self.gnews.search_news(f"{symbol} stock"),
            },
        )

    async def get_mf_nav(self, scheme_code: str) -> dict[str, Any]:
        return await self._fallback_chain(
            data_type="mf_nav",
            identifier=scheme_code,
            ttl=TTL_MF_NAV,
            chain=FALLBACK_CHAIN_MF,
            call_map={
                "mfapi": lambda: self.mfapi.get_nav(scheme_code),
            },
        )

    async def get_filings(
        self,
        symbol: str,
        filing_type: str = "announcements",
    ) -> dict[str, Any]:
        mapping = isin_mapper.resolve(symbol)
        scrip = mapping.bse_scrip_code if mapping else symbol

        method_map: dict[str, Any] = {
            "announcements": lambda: self.bse.get_announcements(scrip),
            "results": lambda: self.bse.get_quarterly_results(scrip),
            "corporate_actions": lambda: self.bse.get_corporate_actions(scrip),
        }
        factory = method_map.get(filing_type, method_map["announcements"])

        return await self._fallback_chain(
            data_type="filings",
            identifier=f"{scrip}:{filing_type}",
            ttl=TTL_FILINGS if TTL_FILINGS > 0 else TTL_FUNDAMENTALS,
            chain=FALLBACK_CHAIN_FILINGS,
            call_map={"bse": factory},
        )

    async def get_macro(self) -> dict[str, Any]:
        return await self._fallback_chain(
            data_type="macro",
            identifier="india",
            ttl=TTL_MACRO,
            chain=FALLBACK_CHAIN_MACRO,
            call_map={
                "rbi_dbie": lambda: self.rbi.get_macro_snapshot(),
            },
        )

    async def get_technical_indicators(
        self,
        symbol: str,
        indicators: list[str] | None = None,
    ) -> dict[str, Any]:
        indicators = indicators or ["RSI", "SMA", "EMA"]
        mapping = isin_mapper.resolve(symbol)
        av_ticker = mapping.alpha_vantage_ticker if mapping else f"{symbol}.BSE"

        results: list[dict[str, Any]] = []
        for ind in indicators:
            data = await self._fallback_chain(
                data_type="technical",
                identifier=f"{symbol}:{ind}",
                ttl=TTL_TECHNICAL_INDICATORS,
                chain=["alpha_vantage"],
                call_map={
                    "alpha_vantage": lambda _ind=ind: self.alpha.get_technical_indicator(
                        av_ticker, _ind
                    ),
                },
            )
            results.append(data)

        return {
            "symbol": symbol,
            "indicators": results,
            "_source": "alpha_vantage",
            "_cache": "mixed",
            "_stale": False,
        }

    async def get_mf_search(self, query: str) -> dict[str, Any]:
        return await self._fallback_chain(
            data_type="mf_search",
            identifier=query,
            ttl=TTL_MF_NAV,
            chain=FALLBACK_CHAIN_MF,
            call_map={
                "mfapi": lambda: self.mfapi.search_schemes(query),
            },
        )

    async def get_earnings_calendar(self, weeks: int = 2) -> dict[str, Any]:
        from_date = datetime.utcnow().strftime("%Y-%m-%d")
        to_date = (datetime.utcnow() + timedelta(weeks=weeks)).strftime("%Y-%m-%d")

        return await self._fallback_chain(
            data_type="earnings",
            identifier=f"{from_date}:{to_date}",
            ttl=TTL_EARNINGS,
            chain=["finnhub"],
            call_map={
                "finnhub": lambda: self.finnhub.get_earnings_calendar(from_date, to_date),
            },
        )

    async def get_shareholding(
        self,
        symbol: str,
        quarters: int = 4,
    ) -> dict[str, Any]:
        mapping = isin_mapper.resolve(symbol)
        scrip = mapping.bse_scrip_code if mapping else symbol
        nse = mapping.nse_symbol if mapping else symbol

        return await self._fallback_chain(
            data_type="shareholding",
            identifier=f"{scrip}:q{quarters}",
            ttl=TTL_SHAREHOLDING,
            chain=["bse", "yfinance"],
            call_map={
                "bse": lambda: self.bse.get_shareholding(scrip),
                "yfinance": lambda: self.yfinance.get_holders(nse),
            },
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        await asyncio.gather(
            self.angel.close(),
            self.alpha.close(),
            self.bse.close(),
            self.finnhub.close(),
            self.gnews.close(),
            self.mfapi.close(),
            self.rbi.close(),
            self.yfinance.close(),
            dual_cache.close(),
            return_exceptions=True,
        )


data_facade = DataFacade()
