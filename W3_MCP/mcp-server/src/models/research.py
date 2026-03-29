"""Pydantic models for PS1 Research Copilot tools and CrewAI outputs."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .common import Citation, Signal


class FinancialStatement(BaseModel):
    period: str
    revenue: float | None = None
    operating_profit: float | None = None
    net_profit: float | None = None
    eps: float | None = None
    total_assets: float | None = None
    total_liabilities: float | None = None
    equity: float | None = None
    cash_flow_operations: float | None = None


class KeyRatios(BaseModel):
    symbol: str
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    roe: float | None = None
    roce: float | None = None
    debt_to_equity: float | None = None
    current_ratio: float | None = None
    dividend_yield: float | None = None
    ev_to_ebitda: float | None = None
    price_to_sales: float | None = None
    sector_avg_pe: float | None = None


class ShareholdingEntry(BaseModel):
    quarter: str
    promoter_pct: float
    fii_pct: float
    dii_pct: float
    retail_pct: float
    others_pct: float = 0.0


class ShareholdingPattern(BaseModel):
    symbol: str
    entries: list[ShareholdingEntry]


class QuarterlyResult(BaseModel):
    symbol: str
    quarter: str
    revenue: float | None = None
    net_profit: float | None = None
    eps: float | None = None
    yoy_revenue_growth: float | None = None
    qoq_revenue_growth: float | None = None
    yoy_profit_growth: float | None = None
    margin_pct: float | None = None


class NewsArticle(BaseModel):
    title: str
    source: str
    url: str
    published_at: str
    summary: str | None = None
    sentiment_score: float | None = Field(default=None, ge=-1.0, le=1.0)


class NewsSentiment(BaseModel):
    symbol: str
    overall_score: float = Field(ge=-1.0, le=1.0)
    article_count: int
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    driver_type: str = Field(description="company_specific | sector | macro")
    key_articles: list[NewsArticle] = []


class CrossSourceAnalysis(BaseModel):
    """Output model for the CrewAI Research Crew synthesizer."""

    symbol: str
    signals: list[Signal]
    contradictions: list[str]
    synthesis: str
    overall_confidence: float = Field(ge=0.0, le=1.0)
    citations: list[Citation]
    disclaimer: str = (
        "This analysis is AI-generated from multiple data sources. "
        "It does not constitute investment advice. Verify independently."
    )


class CompanyComparison(BaseModel):
    symbols: list[str]
    metrics: dict[str, dict[str, float | str | None]]
    summary: str | None = None


class MacroIndicators(BaseModel):
    repo_rate: float | None = None
    reverse_repo_rate: float | None = None
    crr: float | None = None
    slr: float | None = None
    cpi_latest: float | None = None
    wpi_latest: float | None = None
    gdp_growth: float | None = None
    forex_reserves_bn_usd: float | None = None
    usd_inr: float | None = None
    as_of_date: str | None = None


class InflationData(BaseModel):
    entries: list[dict[str, float | str]]
