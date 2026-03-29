"""Shared Pydantic models used across all MCP tool responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SourceMeta(BaseModel):
    """Metadata attached to every tool response."""

    source: str = Field(description="API name that provided the data")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    cache_status: str = Field(default="miss", description="hit | miss | stale")


class ToolResponse(BaseModel):
    """Base response wrapper for all MCP tools."""

    data: Any
    meta: SourceMeta
    disclaimer: str = Field(
        default=(
            "This data is for informational purposes only and does not constitute "
            "investment advice. Verify all data independently before making decisions."
        )
    )


class ErrorResponse(BaseModel):
    """Structured error returned instead of raising exceptions."""

    error: str
    error_code: str = "INTERNAL_ERROR"
    fallback_data: Any | None = None
    meta: SourceMeta | None = None


class Citation(BaseModel):
    """Source citation for cross-source reasoning outputs."""

    source: str
    data_point: str
    value: str
    timestamp: str


class Signal(BaseModel):
    """A single directional signal from one data source."""

    source: str = Field(description="e.g. 'Angel One API', 'Finnhub'")
    signal_type: str = Field(description="price | fundamental | sentiment | macro")
    direction: float = Field(ge=-1.0, le=1.0, description="-1 bearish to +1 bullish")
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str
    timestamp: str


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses."""

    page: int = 1
    page_size: int = 20
    total_items: int = 0
    has_more: bool = False
