"""
Local tips and hidden gems (Reddit, curated, LLM).
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class LocalTip(BaseModel):
    """Local insider tip from Reddit or curated DB."""

    title: str = Field(...)
    content: str = Field(...)
    category: str = Field(..., description="e.g. food, safety, transport")
    source_platform: str = Field(..., description="e.g. reddit, curated")
    source_url: Optional[str] = Field(default=None)
    upvotes: int = Field(default=0, ge=0)
    source: Literal["api", "curated", "llm"] = Field(...)
    verified: bool = Field(default=False)


class HiddenGem(BaseModel):
    """Hidden gem or lesser-known spot."""

    name: str = Field(...)
    description: str = Field(...)
    why_special: Optional[str] = Field(default=None)
    pro_tip: Optional[str] = Field(default=None)
    category: str = Field(...)
    latitude: Optional[float] = Field(default=None)
    longitude: Optional[float] = Field(default=None)
    confidence: float = Field(default=1.0, ge=0, le=1, description="Confidence score 0-1")
    source: Literal["api", "curated", "llm"] = Field(...)
    verified: bool = Field(default=False)
