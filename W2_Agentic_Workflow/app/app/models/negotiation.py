"""
Negotiation models for the AI Travel Negotiator (Trade-Off Negotiation Engine).

Three bundle types: Budget Saver, Best Value, Experience Max.
Each bundle contains a full cost breakdown, experience score, trade-off lines,
rejected alternatives, and booking links.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class MoneyBreakdown(BaseModel):
    """Itemised cost breakdown for a bundle."""

    transport: float = Field(..., ge=0, description="Transport cost (flight/train/bus)")
    stay: float = Field(..., ge=0, description="Accommodation cost")
    activities: float = Field(..., ge=0, description="Sum of activity entry fees")
    food: float = Field(..., ge=0, description="Estimated food/meals budget")
    buffer: float = Field(..., ge=0, description="Contingency / misc buffer")
    total: float = Field(..., ge=0, description="Grand total")

    @field_validator("total", mode="before")
    @classmethod
    def _auto_total(cls, v: float, info: Any) -> float:
        """Auto-compute total if 0 and components are present."""
        if v == 0 and info.data:
            d = info.data
            return (
                d.get("transport", 0)
                + d.get("stay", 0)
                + d.get("activities", 0)
                + d.get("food", 0)
                + d.get("buffer", 0)
            )
        return v


class TradeOffLine(BaseModel):
    """A single gain/sacrifice trade-off bullet."""

    gain: str = Field(..., description="What you gain with this bundle")
    sacrifice: str = Field(..., description="What you give up")


class RejectedOption(BaseModel):
    """An alternative that was considered but rejected."""

    name: str = Field(..., description="Option name (e.g. 'IndiGo flight', '5-star hotel')")
    reason: str = Field(..., description="Short reason for rejection")


class BundleChoice(BaseModel):
    """A complete negotiated travel bundle."""

    id: str = Field(..., description="Unique bundle id: budget_saver | best_value | experience_max")
    title: str = Field(..., description="Human-friendly title")
    summary: str = Field(..., description="One-line summary of the bundle's character")

    # Selected options (stored as dicts to stay compatible with existing state dicts)
    transport: Dict[str, Any] = Field(..., description="Selected transport option dict")
    stay: Dict[str, Any] = Field(..., description="Selected hotel/stay option dict")
    activities: List[Dict[str, Any]] = Field(default_factory=list, description="Selected activities (3-7)")

    # Financials
    breakdown: MoneyBreakdown = Field(..., description="Full cost breakdown")

    # Scores (0–100)
    experience_score: int = Field(..., ge=0, le=100, description="Experience quality score")
    cost_score: int = Field(..., ge=0, le=100, description="Cost efficiency score (higher = cheaper)")
    convenience_score: int = Field(..., ge=0, le=100, description="Convenience / feasibility score")
    final_score: float = Field(..., ge=0, le=100, description="Weighted composite score")

    # Narrative
    tradeoffs: List[TradeOffLine] = Field(default_factory=list, description="3-5 trade-off bullets")
    rejected: List[RejectedOption] = Field(default_factory=list, description="1-2 rejected alternatives")
    booking_links: Dict[str, Optional[str]] = Field(
        default_factory=dict,
        description="Booking links keyed by category: transport, stay, activity_<n>",
    )
    decision_log: List[str] = Field(default_factory=list, description="Transparency log for this bundle")


# ---------------------------------------------------------------------------
# What-If request
# ---------------------------------------------------------------------------


class WhatIfRequest(BaseModel):
    """A budget adjustment request from the user."""

    delta_budget: int = Field(..., description="Budget change in INR (positive = increase)")
    applied_at_stage: str = Field(default="negotiator", description="Graph stage when applied")
    resulting_bundle_ids: List[str] = Field(
        default_factory=list, description="Bundle IDs generated after this adjustment"
    )


# ---------------------------------------------------------------------------
# Feasibility result
# ---------------------------------------------------------------------------


class FeasibilityResult(BaseModel):
    """Result of feasibility validation for a bundle."""

    bundle_id: str
    passed: bool
    issues: List[str] = Field(default_factory=list)
    suggested_tweaks: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Negotiation scoring weights (tweakable constants)
# ---------------------------------------------------------------------------


class ScoringWeights(BaseModel):
    """Weights for final bundle score = w_exp * exp + w_cost * cost + w_conv * conv."""

    w_experience: float = Field(default=0.45)
    w_cost: float = Field(default=0.35)
    w_convenience: float = Field(default=0.20)

    def compute(self, experience: float, cost: float, convenience: float) -> float:
        raw = (
            self.w_experience * experience
            + self.w_cost * cost
            + self.w_convenience * convenience
        )
        return round(min(100.0, max(0.0, raw)), 2)


# ---------------------------------------------------------------------------
# Bundle type literal
# ---------------------------------------------------------------------------

BundleType = Literal["budget_saver", "best_value", "experience_max"]

BUNDLE_META: Dict[BundleType, Dict[str, str]] = {
    "budget_saver": {
        "title": "Budget Saver",
        "summary": "Cheapest viable option — every rupee counts",
        "icon": "💰",
        "color": "#2D8B5F",
    },
    "best_value": {
        "title": "Best Value",
        "summary": "Balanced experience at the optimal price point",
        "icon": "⚖️",
        "color": "#1E3A6E",
    },
    "experience_max": {
        "title": "Experience Max",
        "summary": "Maximum richness — up to +10% over budget",
        "icon": "✨",
        "color": "#6B3FA0",
    },
}
