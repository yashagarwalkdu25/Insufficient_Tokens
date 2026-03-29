"""Pydantic models for market data tools."""

from __future__ import annotations

from pydantic import BaseModel, Field


class StockQuote(BaseModel):
    symbol: str
    isin: str | None = None
    exchange: str = "NSE"
    ltp: float = Field(description="Last traded price")
    change: float = Field(description="Absolute change from previous close")
    change_pct: float = Field(description="Percentage change")
    open: float
    high: float
    low: float
    close: float = Field(description="Previous close")
    volume: int
    market_cap: float | None = None
    pe_ratio: float | None = None
    week_52_high: float | None = None
    week_52_low: float | None = None


class OHLCVBar(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class PriceHistory(BaseModel):
    symbol: str
    interval: str
    bars: list[OHLCVBar]


class IndexData(BaseModel):
    index_name: str
    value: float
    change: float
    change_pct: float
    advances: int | None = None
    declines: int | None = None
    top_gainers: list[StockQuote] = []
    top_losers: list[StockQuote] = []


class TechnicalIndicator(BaseModel):
    name: str
    value: float
    signal: str = Field(description="buy | sell | neutral")


class TechnicalIndicators(BaseModel):
    symbol: str
    indicators: list[TechnicalIndicator]


class MoverStock(BaseModel):
    symbol: str
    ltp: float
    change_pct: float
    volume: int


class TopMovers(BaseModel):
    exchange: str
    gainers: list[MoverStock]
    losers: list[MoverStock]
