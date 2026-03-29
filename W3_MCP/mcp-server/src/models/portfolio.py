"""Pydantic models for PS2 Portfolio Risk Monitor tools."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .common import Citation, Signal


class PortfolioHolding(BaseModel):
    symbol: str
    isin: str | None = None
    quantity: int
    avg_price: float
    current_price: float | None = None
    current_value: float | None = None
    pnl: float | None = None
    pnl_pct: float | None = None
    weight_pct: float | None = None
    sector: str | None = None


class PortfolioSummary(BaseModel):
    user_id: str
    holdings: list[PortfolioHolding]
    total_invested: float
    current_value: float
    total_pnl: float
    total_pnl_pct: float
    sector_allocation: dict[str, float] = {}


class RiskAlert(BaseModel):
    alert_type: str = Field(description="concentration | sector_tilt | sentiment_shift | macro_risk")
    severity: str = Field(description="low | medium | high | critical")
    message: str
    details: dict[str, str | float] = {}


class PortfolioHealthCheck(BaseModel):
    user_id: str
    risk_score: float = Field(ge=0.0, le=100.0)
    alerts: list[RiskAlert]
    concentration_flags: list[str] = []
    sector_exposure: dict[str, float] = {}


class MFOverlap(BaseModel):
    holding_symbol: str
    overlapping_funds: list[str]
    overlap_score: float


class PortfolioRiskReport(BaseModel):
    """Output model for the CrewAI Risk Crew narrator."""

    user_id: str
    risk_score: float = Field(ge=0.0, le=100.0)
    signals: list[Signal]
    alerts: list[RiskAlert]
    contradictions: list[str]
    narrative: str
    citations: list[Citation]
    recommendations: list[str] = []
    disclaimer: str = (
        "This risk analysis is AI-generated and does not constitute investment advice. "
        "Portfolio risk assessment is indicative only."
    )


class WhatIfResult(BaseModel):
    scenario: str
    portfolio_impact_pct: float
    per_stock_impact: dict[str, float]
    narrative: str
