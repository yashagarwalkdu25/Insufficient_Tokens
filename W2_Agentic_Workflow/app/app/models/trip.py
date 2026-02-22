"""
Trip, day plan, and itinerary item models.
"""
from __future__ import annotations

from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

# Type alias to avoid shadowing the field name "date"
DateType = date


class ItineraryItem(BaseModel):
    """Single item in a day plan (transport, activity, meal, hotel, free_time)."""

    time: str = Field(..., description="Start time e.g. 09:00")
    end_time: Optional[str] = Field(default=None)
    title: str = Field(...)
    description: Optional[str] = Field(default=None)
    item_type: Literal["transport", "activity", "meal", "hotel", "free_time"] = Field(...)
    cost: float = Field(default=0, ge=0)
    currency: str = Field(default="INR")
    location: Optional[str] = Field(default=None)
    latitude: Optional[float] = Field(default=None)
    longitude: Optional[float] = Field(default=None)
    booking_url: Optional[str] = Field(default=None)
    source: Literal["api", "curated", "llm"] = Field(...)
    verified: bool = Field(default=False)
    notes: Optional[str] = Field(default=None)
    travel_duration_to_next: Optional[int] = Field(default=None, description="Minutes to next activity")
    travel_mode_to_next: Optional[str] = Field(default=None, description="auto / walk / bus / train")
    contact_info: Optional[str] = Field(default=None, description="Phone + address for booking")


class DayPlan(BaseModel):
    """One day of the itinerary."""

    day_number: int = Field(..., ge=1)
    date: DateType = Field(...)
    title: Optional[str] = Field(default=None)
    items: List[ItineraryItem] = Field(default_factory=list)
    day_cost: float = Field(default=0, ge=0)
    weather_summary: Optional[str] = Field(default=None)
    tip_of_the_day: Optional[str] = Field(default=None)


class Trip(BaseModel):
    """Full trip with day plans and metadata."""

    destination: str = Field(...)
    origin: str = Field(...)
    start_date: DateType = Field(...)
    end_date: DateType = Field(...)
    days: List[DayPlan] = Field(default_factory=list)
    total_cost: float = Field(default=0, ge=0)
    currency: str = Field(default="INR")
    traveler_type: str = Field(default="solo")
    travel_style: str = Field(default="balanced")
