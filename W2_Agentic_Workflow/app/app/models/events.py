"""
Events and vibe score models.
"""
from __future__ import annotations

from datetime import date
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class Event(BaseModel):
    """Festival or event affecting the trip."""

    name: str = Field(...)
    description: Optional[str] = Field(default=None)
    start_date: date = Field(...)
    end_date: date = Field(...)
    location: str = Field(...)
    event_type: str = Field(..., description="e.g. festival, holiday, sports")
    impact: Literal["positive", "negative", "neutral"] = Field(...)
    recommendation: Optional[str] = Field(default=None)
    source: Literal["api", "curated", "llm"] = Field(...)
    verified: bool = Field(default=False)


class VibeScore(BaseModel):
    """Match score between itinerary and user preferences."""

    overall_score: int = Field(..., ge=0, le=100, description="0-100")
    breakdown: Dict[str, int] = Field(default_factory=dict, description="e.g. adventure: 92, culture: 78")
    tagline: str = Field(..., description="Short tagline for the trip")
    perfect_matches: List[str] = Field(default_factory=list)
    considerations: List[str] = Field(default_factory=list)
