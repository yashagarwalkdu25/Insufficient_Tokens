"""Pydantic models for PS3 Earnings Command Center tools."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .common import Citation, Signal


class EarningsCalendarEntry(BaseModel):
    symbol: str
    company_name: str
    expected_date: str
    quarter: str
    previous_eps: float | None = None


class EarningsCalendar(BaseModel):
    entries: list[EarningsCalendarEntry]
    period_weeks: int


class EPSHistoryEntry(BaseModel):
    quarter: str
    eps_actual: float | None = None
    eps_estimated: float | None = None
    surprise_pct: float | None = None
    revenue: float | None = None


class EPSHistory(BaseModel):
    symbol: str
    entries: list[EPSHistoryEntry]


class PreEarningsProfile(BaseModel):
    symbol: str
    last_4_quarters: list[EPSHistoryEntry]
    key_ratios: dict[str, float | None] = {}
    shareholding_trend: dict[str, float] = {}
    news_sentiment_score: float | None = None
    options_pcr: float | None = Field(default=None, description="Put-Call Ratio")


class AnalystExpectation(BaseModel):
    symbol: str
    consensus_eps: float | None = None
    consensus_revenue: float | None = None
    num_analysts: int = 0
    high_estimate: float | None = None
    low_estimate: float | None = None
    source: str = "extrapolated"


class PostResultsReaction(BaseModel):
    symbol: str
    filing_date: str
    price_on_result_day: float | None = None
    price_change_day0: float | None = None
    price_change_day1: float | None = None
    price_change_day2: float | None = None
    volume_spike_pct: float | None = None


class EarningsBeatMiss(BaseModel):
    symbol: str
    verdict: str = Field(description="beat | miss | inline")
    actual_eps: float | None = None
    expected_eps: float | None = None
    surprise_pct: float | None = None
    actual_revenue: float | None = None
    expected_revenue: float | None = None


class EarningsVerdict(BaseModel):
    """Output model for the CrewAI Earnings Crew narrator."""

    symbol: str
    quarter: str
    beat_miss: str = Field(description="beat | miss | inline")
    signals: list[Signal]
    filing_highlights: dict[str, float | str | None] = {}
    market_reaction: PostResultsReaction | None = None
    contradictions: list[str] = []
    narrative: str
    citations: list[Citation]
    disclaimer: str = (
        "Earnings analysis is AI-generated from public filings and market data. "
        "Not investment advice."
    )


class EarningsSeasonDashboard(BaseModel):
    week_date: str
    companies_reported: int
    beats: int
    misses: int
    inlines: int
    sector_trends: dict[str, str] = {}
    notable_surprises: list[EarningsBeatMiss] = []


class OptionChainEntry(BaseModel):
    strike_price: float
    call_oi: int | None = None
    put_oi: int | None = None
    call_ltp: float | None = None
    put_ltp: float | None = None
    call_iv: float | None = None
    put_iv: float | None = None


class OptionChain(BaseModel):
    symbol: str
    expiry: str
    entries: list[OptionChainEntry]
    pcr: float | None = None
    max_pain: float | None = None
