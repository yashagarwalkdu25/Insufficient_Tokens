"""yfinance fallback adapter (P3 priority) with exponential backoff."""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_MAX_RETRIES = 3
_BACKOFF_BASE = 1.0


class YFinanceAdapter:
    """Wraps the ``yfinance`` library as an async-compatible fallback.

    Marked as **P3** — used only when primary sources fail.
    All calls run yfinance synchronously in a thread executor with
    exponential backoff on failure.
    """

    async def _run_with_backoff(self, func: Any, *args: Any) -> Any:
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(None, func, *args)
            except Exception as exc:
                last_exc = exc
                wait = _BACKOFF_BASE * (2 ** attempt)
                logger.warning(
                    "yfinance.retry",
                    attempt=attempt + 1,
                    wait=wait,
                    error=str(exc),
                )
                await asyncio.sleep(wait)
        raise last_exc  # type: ignore[misc]

    def _fetch_quote(self, symbol: str) -> dict[str, Any]:
        import yfinance as yf

        ticker = yf.Ticker(f"{symbol}.NS")
        info = ticker.info or {}
        return {
            "symbol": symbol,
            "ltp": info.get("regularMarketPrice", 0.0),
            "change": info.get("regularMarketChange", 0.0),
            "change_pct": info.get("regularMarketChangePercent", 0.0),
            "open": info.get("regularMarketOpen", 0.0),
            "high": info.get("regularMarketDayHigh", 0.0),
            "low": info.get("regularMarketDayLow", 0.0),
            "close": info.get("regularMarketPreviousClose", 0.0),
            "volume": info.get("regularMarketVolume", 0),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "week_52_high": info.get("fiftyTwoWeekHigh"),
            "week_52_low": info.get("fiftyTwoWeekLow"),
            "exchange": "NSE",
            "_source": "yfinance",
        }

    async def get_quote(self, symbol: str) -> dict[str, Any]:
        """Fetch real-time quote via yfinance with .NS suffix."""
        try:
            return await self._run_with_backoff(self._fetch_quote, symbol)
        except Exception as exc:
            logger.error("yfinance.quote.error", symbol=symbol, error=str(exc))
            return {"error": str(exc), "error_code": "YF_QUOTE_FAILED", "_source": "yfinance"}

    def _fetch_historical(self, symbol: str, period: str, interval: str) -> dict[str, Any]:
        import yfinance as yf

        ticker = yf.Ticker(f"{symbol}.NS")
        df = ticker.history(period=period, interval=interval)
        bars = [
            {
                "date": str(idx.date()) if hasattr(idx, "date") else str(idx),
                "open": round(row["Open"], 2),
                "high": round(row["High"], 2),
                "low": round(row["Low"], 2),
                "close": round(row["Close"], 2),
                "volume": int(row["Volume"]),
            }
            for idx, row in df.iterrows()
        ]
        return {"symbol": symbol, "period": period, "interval": interval, "bars": bars, "_source": "yfinance"}

    async def get_historical(
        self,
        symbol: str,
        period: str = "1mo",
        interval: str = "1d",
    ) -> dict[str, Any]:
        """Fetch historical OHLCV data."""
        try:
            return await self._run_with_backoff(self._fetch_historical, symbol, period, interval)
        except Exception as exc:
            logger.error("yfinance.historical.error", symbol=symbol, error=str(exc))
            return {"error": str(exc), "error_code": "YF_HISTORICAL_FAILED", "_source": "yfinance"}

    def _fetch_financials(self, symbol: str) -> dict[str, Any]:
        import yfinance as yf

        ticker = yf.Ticker(f"{symbol}.NS")
        income = ticker.financials
        balance = ticker.balance_sheet
        cashflow = ticker.cashflow
        return {
            "symbol": symbol,
            "income_statement": income.to_dict() if income is not None else {},
            "balance_sheet": balance.to_dict() if balance is not None else {},
            "cashflow": cashflow.to_dict() if cashflow is not None else {},
            "_source": "yfinance",
        }

    async def get_financials(self, symbol: str) -> dict[str, Any]:
        """Fetch financial statements."""
        try:
            return await self._run_with_backoff(self._fetch_financials, symbol)
        except Exception as exc:
            logger.error("yfinance.financials.error", symbol=symbol, error=str(exc))
            return {"error": str(exc), "error_code": "YF_FINANCIALS_FAILED", "_source": "yfinance"}

    def _fetch_overview(self, symbol: str) -> dict[str, Any]:
        import yfinance as yf

        ticker = yf.Ticker(f"{symbol}.NS")
        info = ticker.info or {}

        def _safe_float(key: str) -> float | None:
            v = info.get(key)
            if v is None:
                return None
            try:
                return float(v)
            except (ValueError, TypeError):
                return None

        return {
            "symbol": symbol,
            "pe_ratio": _safe_float("trailingPE"),
            "pb_ratio": _safe_float("priceToBook"),
            "roe": _safe_float("returnOnEquity"),
            "roce": None,
            "debt_to_equity": _safe_float("debtToEquity"),
            "current_ratio": _safe_float("currentRatio"),
            "dividend_yield": _safe_float("dividendYield"),
            "ev_to_ebitda": _safe_float("enterpriseToEbitda"),
            "price_to_sales": _safe_float("priceToSalesTrailing12Months"),
            "eps": _safe_float("trailingEps"),
            "sector_avg_pe": None,
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": _safe_float("marketCap"),
            "_source": "yfinance",
        }

    async def get_overview(self, symbol: str) -> dict[str, Any]:
        """Fetch company overview with key ratios from ticker.info."""
        try:
            return await self._run_with_backoff(self._fetch_overview, symbol)
        except Exception as exc:
            logger.error("yfinance.overview.error", symbol=symbol, error=str(exc))
            return {"error": str(exc), "error_code": "YF_OVERVIEW_FAILED", "_source": "yfinance"}

    def _fetch_holders(self, symbol: str) -> dict[str, Any]:
        import yfinance as yf

        ticker = yf.Ticker(f"{symbol}.NS")
        holders = ticker.major_holders
        inst = ticker.institutional_holders

        result: dict[str, Any] = {
            "symbol": symbol,
            "entries": [],
            "_source": "yfinance",
        }

        if holders is not None and not holders.empty:
            pct_held_insiders = None
            pct_held_institutions = None
            try:
                for _, row in holders.iterrows():
                    label = str(row.iloc[1]).lower() if len(row) > 1 else ""
                    val = row.iloc[0]
                    if "insider" in label:
                        pct_held_insiders = float(str(val).replace("%", ""))
                    elif "institution" in label:
                        pct_held_institutions = float(str(val).replace("%", ""))
            except Exception:
                pass

            promoter = pct_held_insiders or 0.0
            fii = (pct_held_institutions or 0.0) * 0.6
            dii = (pct_held_institutions or 0.0) * 0.4
            retail = max(0.0, 100.0 - promoter - fii - dii)

            result["entries"] = [{
                "quarter": "latest",
                "promoter": round(promoter, 2),
                "fii": round(fii, 2),
                "dii": round(dii, 2),
                "retail": round(retail, 2),
            }]

        return result

    async def get_holders(self, symbol: str) -> dict[str, Any]:
        """Fetch major holders / shareholding approximation."""
        try:
            return await self._run_with_backoff(self._fetch_holders, symbol)
        except Exception as exc:
            logger.error("yfinance.holders.error", symbol=symbol, error=str(exc))
            return {"error": str(exc), "error_code": "YF_HOLDERS_FAILED", "_source": "yfinance"}

    def _fetch_quarterly_earnings(self, symbol: str) -> dict[str, Any]:
        import yfinance as yf
        import math

        ticker = yf.Ticker(f"{symbol}.NS")
        history: list[dict[str, Any]] = []

        # --- Strategy 1: quarterly_income_stmt (most reliable for Indian stocks) ---
        qi = getattr(ticker, "quarterly_income_stmt", None)
        if qi is not None and not qi.empty:
            for col in qi.columns:
                quarter_label = col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)[:10]
                eps_val = None
                rev_val = None
                net_income = None
                for eps_key in ("Diluted EPS", "Basic EPS"):
                    if eps_key in qi.index:
                        raw = qi.at[eps_key, col]
                        if raw is not None and not (isinstance(raw, float) and math.isnan(raw)):
                            eps_val = float(raw)
                            break
                for rev_key in ("Total Revenue", "Operating Revenue", "Revenue"):
                    if rev_key in qi.index:
                        raw = qi.at[rev_key, col]
                        if raw is not None and not (isinstance(raw, float) and math.isnan(raw)):
                            rev_val = float(raw)
                            break
                for ni_key in ("Net Income", "Net Income Common Stockholders"):
                    if ni_key in qi.index:
                        raw = qi.at[ni_key, col]
                        if raw is not None and not (isinstance(raw, float) and math.isnan(raw)):
                            net_income = float(raw)
                            break
                if eps_val is not None or rev_val is not None:
                    history.append({
                        "quarter": quarter_label,
                        "eps": eps_val,
                        "revenue": rev_val,
                        "net_income": net_income,
                    })

        # --- Strategy 2: Fall back to quarterly_earnings if income_stmt was empty ---
        if not history:
            qe = getattr(ticker, "quarterly_earnings", None)
            if qe is not None and not qe.empty:
                for idx, row in qe.iterrows():
                    quarter_label = str(idx)
                    eps_val = row.get("Earnings") if "Earnings" in row.index else row.get("EPS")
                    rev_val = row.get("Revenue")
                    if eps_val is not None or rev_val is not None:
                        history.append({
                            "quarter": quarter_label,
                            "eps": float(eps_val) if eps_val is not None else None,
                            "revenue": float(rev_val) if rev_val is not None else None,
                            "net_income": None,
                        })

        # --- Strategy 3: Fall back to quarterly_financials ---
        if not history:
            qf = getattr(ticker, "quarterly_financials", None)
            if qf is not None and not qf.empty:
                for col in qf.columns:
                    quarter_label = col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)[:10]
                    eps_val = None
                    rev_val = None
                    for eps_key in ("Basic EPS", "Diluted EPS"):
                        if eps_key in qf.index:
                            raw = qf.at[eps_key, col]
                            if raw is not None and not (isinstance(raw, float) and math.isnan(raw)):
                                eps_val = float(raw)
                                break
                    for rev_key in ("Total Revenue", "Operating Revenue"):
                        if rev_key in qf.index:
                            raw = qf.at[rev_key, col]
                            if raw is not None and not (isinstance(raw, float) and math.isnan(raw)):
                                rev_val = float(raw)
                                break
                    if eps_val is not None or rev_val is not None:
                        history.append({
                            "quarter": quarter_label,
                            "eps": eps_val,
                            "revenue": rev_val,
                            "net_income": None,
                        })

        # Columns come newest-first; reverse so oldest is first
        history = list(reversed(history))
        return {
            "symbol": symbol,
            "quarterly_earnings": history,
            "_source": "yfinance",
        }

    async def get_quarterly_earnings(self, symbol: str) -> dict[str, Any]:
        """Fetch quarterly earnings history (EPS + revenue per quarter)."""
        try:
            return await self._run_with_backoff(self._fetch_quarterly_earnings, symbol)
        except Exception as exc:
            logger.error("yfinance.quarterly_earnings.error", symbol=symbol, error=str(exc))
            return {"error": str(exc), "_source": "yfinance"}

    def _fetch_options(self, symbol: str) -> dict[str, Any]:
        import yfinance as yf

        ticker = yf.Ticker(f"{symbol}.NS")
        expiries = ticker.options
        if not expiries:
            return {"symbol": symbol, "expiries": [], "chains": {}, "_source": "yfinance"}

        nearest = expiries[0]
        chain = ticker.option_chain(nearest)
        calls_data: list[dict[str, Any]] = []
        puts_data: list[dict[str, Any]] = []

        if chain.calls is not None and not chain.calls.empty:
            for _, r in chain.calls.head(20).iterrows():
                calls_data.append({
                    "strike": float(r.get("strike", 0)),
                    "ltp": float(r.get("lastPrice", 0)),
                    "oi": int(r.get("openInterest", 0)),
                    "volume": int(r.get("volume", 0)),
                    "iv": float(r.get("impliedVolatility", 0)),
                })
        if chain.puts is not None and not chain.puts.empty:
            for _, r in chain.puts.head(20).iterrows():
                puts_data.append({
                    "strike": float(r.get("strike", 0)),
                    "ltp": float(r.get("lastPrice", 0)),
                    "oi": int(r.get("openInterest", 0)),
                    "volume": int(r.get("volume", 0)),
                    "iv": float(r.get("impliedVolatility", 0)),
                })

        total_call_oi = sum(c["oi"] for c in calls_data)
        total_put_oi = sum(p["oi"] for p in puts_data)
        pcr = round(total_put_oi / max(total_call_oi, 1), 3)
        max_pain_strike = None
        if puts_data:
            max_pain_strike = max(puts_data, key=lambda x: x["oi"])["strike"]

        return {
            "symbol": symbol,
            "expiry": nearest,
            "calls": calls_data,
            "puts": puts_data,
            "pcr": pcr,
            "max_pain": max_pain_strike,
            "total_call_oi": total_call_oi,
            "total_put_oi": total_put_oi,
            "_source": "yfinance",
        }

    async def get_options(self, symbol: str) -> dict[str, Any]:
        """Fetch option chain for nearest expiry."""
        try:
            return await self._run_with_backoff(self._fetch_options, symbol)
        except Exception as exc:
            logger.error("yfinance.options.error", symbol=symbol, error=str(exc))
            return {"error": str(exc), "_source": "yfinance"}

    async def close(self) -> None:
        pass
