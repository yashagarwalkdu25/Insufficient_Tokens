"""
Activity and restaurant models.
"""
from __future__ import annotations

from typing import Dict, Literal, Optional

from pydantic import BaseModel, Field


class Activity(BaseModel):
    """Activity or attraction with opening hours and contact."""

    name: str = Field(...)
    description: Optional[str] = Field(default=None)
    category: str = Field(..., description="e.g. adventure, culture, nature")
    duration_hours: float = Field(..., ge=0)
    price: float = Field(..., ge=0)
    currency: str = Field(default="INR")
    latitude: Optional[float] = Field(default=None)
    longitude: Optional[float] = Field(default=None)
    rating: Optional[float] = Field(default=None, ge=0, le=5)
    address: Optional[str] = Field(default=None)
    booking_url: Optional[str] = Field(default=None)
    opening_hours: Optional[Dict[str, str]] = Field(
        default=None,
        description='e.g. {"Monday": "09:00-18:00", "Tuesday": "09:00-18:00"}',
    )
    phone: Optional[str] = Field(default=None)
    best_time: Optional[str] = Field(default=None, description="Recommended time of day")
    source: Literal["api", "curated", "llm", "tavily_web"] = Field(...)
    verified: bool = Field(default=False)


class Restaurant(BaseModel):
    """Restaurant or meal option."""

    name: str = Field(...)
    cuisine: str = Field(...)
    price_level: Optional[str] = Field(default=None, description="e.g. $, $$, $$$")
    rating: Optional[float] = Field(default=None, ge=0, le=5)
    address: Optional[str] = Field(default=None)
    latitude: Optional[float] = Field(default=None)
    longitude: Optional[float] = Field(default=None)
    phone: Optional[str] = Field(default=None)
    opening_hours: Optional[Dict[str, str]] = Field(default=None)
    source: Literal["api", "curated", "llm", "tavily_web"] = Field(...)
    verified: bool = Field(default=False)
