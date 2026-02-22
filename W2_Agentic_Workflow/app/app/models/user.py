"""
User and trip request models.
"""
from __future__ import annotations

from datetime import date
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class TripRequest(BaseModel):
    """User trip request with budget allocation by style."""

    destination: str = Field(..., description="Destination city or region")
    origin: str = Field(..., description="Origin city or airport")
    start_date: date = Field(..., description="Trip start date")
    end_date: date = Field(..., description="Trip end date")
    budget: float = Field(..., ge=0, description="Total budget amount")
    currency: str = Field(default="INR", description="Currency code")
    traveler_type: str = Field(default="solo", description="solo / couple / family / group")
    travel_style: str = Field(default="balanced", description="backpacker / budget / balanced / luxury")
    interests: List[str] = Field(default_factory=list, description="Interest tags")
    num_travelers: int = Field(default=1, ge=1, description="Number of travelers")
    special_requirements: Optional[str] = Field(default=None, description="Accessibility, dietary, etc.")

    @property
    def duration_days(self) -> int:
        """Number of days (inclusive)."""
        delta = self.end_date - self.start_date
        return max(1, delta.days + 1)

    def get_budget_allocation(self, style: Optional[str] = None) -> Dict[str, float]:
        """
        Return category percentages for the given style (default: self.travel_style).
        Keys: transport, accommodation, activities, meals, misc.
        """
        style = style or self.travel_style
        allocations: Dict[str, Dict[str, float]] = {
            "backpacker": {"transport": 0.35, "accommodation": 0.25, "activities": 0.20, "meals": 0.15, "misc": 0.05},
            "budget": {"transport": 0.30, "accommodation": 0.30, "activities": 0.20, "meals": 0.15, "misc": 0.05},
            "balanced": {"transport": 0.25, "accommodation": 0.35, "activities": 0.22, "meals": 0.13, "misc": 0.05},
            "luxury": {"transport": 0.20, "accommodation": 0.45, "activities": 0.20, "meals": 0.12, "misc": 0.03},
        }
        return allocations.get(style, allocations["balanced"])
