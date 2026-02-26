"""
Accommodation (hotel) model.
"""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class HotelOption(BaseModel):
    """Hotel or stay option with contact and booking info."""

    name: str = Field(..., description="Hotel name")
    address: Optional[str] = Field(default=None)
    latitude: Optional[float] = Field(default=None)
    longitude: Optional[float] = Field(default=None)
    star_rating: Optional[float] = Field(default=None, ge=0, le=5)
    price_per_night: float = Field(..., ge=0)
    total_price: float = Field(..., ge=0)
    currency: str = Field(default="INR")
    amenities: List[str] = Field(default_factory=list)
    booking_url: Optional[str] = Field(default=None)
    image_url: Optional[str] = Field(default=None)
    phone: Optional[str] = Field(default=None)
    email: Optional[str] = Field(default=None)
    contact_info: Optional[str] = Field(default=None, description="Combined phone/address for display")
    check_in_time: Optional[str] = Field(default=None)
    check_out_time: Optional[str] = Field(default=None)
    source: Literal["api", "curated", "llm", "estimated", "tavily_web"] = Field(...)
    verified: bool = Field(default=False)
