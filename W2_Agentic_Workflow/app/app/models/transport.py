"""
Transport models: flights and ground (train/bus).
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class TransportType(str, Enum):
    FLIGHT = "flight"
    TRAIN = "train"
    BUS = "bus"


class FlightSegment(BaseModel):
    """Single flight leg."""

    airline: str = Field(..., description="Airline name or code")
    flight_number: str = Field(..., description="Flight number")
    departure_airport: str = Field(..., description="IATA or airport code")
    arrival_airport: str = Field(..., description="IATA or airport code")
    departure_time: datetime = Field(..., description="Departure datetime")
    arrival_time: datetime = Field(..., description="Arrival datetime")
    duration_minutes: int = Field(..., ge=0, description="Duration in minutes")


class FlightOption(BaseModel):
    """Round-trip or one-way flight option."""

    outbound: FlightSegment = Field(..., description="Outbound segment")
    return_segment: Optional[FlightSegment] = Field(default=None, alias="return", description="Return segment")
    total_price: float = Field(..., ge=0)
    currency: str = Field(default="INR")
    booking_url: Optional[str] = Field(default=None)
    source: Literal["api", "curated", "llm", "tavily_web"] = Field(..., description="Data source")
    verified: bool = Field(default=False, description="Verified against real data")

    model_config = {"populate_by_name": True}


class GroundTransportOption(BaseModel):
    """Train or bus option."""

    transport_type: TransportType = Field(..., description="train or bus")
    operator: str = Field(..., description="Operator name e.g. IRCTC, RedBus")
    departure_time: datetime = Field(...)
    arrival_time: datetime = Field(...)
    duration_minutes: int = Field(..., ge=0)
    price: float = Field(..., ge=0)
    currency: str = Field(default="INR")
    booking_url: Optional[str] = Field(default=None)
    source: Literal["api", "curated", "llm", "tavily_web"] = Field(...)
    verified: bool = Field(default=False)
