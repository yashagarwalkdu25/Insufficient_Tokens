"""
Travel planner state for LangGraph.
Custom reducer for list fields: merge and deduplicate by key (no operator.add).
"""
from __future__ import annotations

from typing import Annotated, Any, Optional, TypedDict


def _dedupe_reducer(current: list[Any], update: Optional[list[Any]]) -> list[Any]:
    """Merge lists and deduplicate by id/name or str(item). Don't use operator.add."""
    if update is None:
        return current or []
    if not isinstance(update, list):
        return current or []
    seen: set[str] = set()
    out: list[Any] = []
    for item in (current or []) + update:
        if isinstance(item, dict):
            key = item.get("id") or item.get("name") or item.get("title") or str(item)
        else:
            key = str(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


class TravelPlannerState(TypedDict, total=False):
    """Full state for the travel planning graph."""

    user_id: str
    session_id: str
    raw_query: str
    trip_request: Optional[dict]
    intent_type: str
    current_stage: str
    requires_approval: bool
    approval_type: Optional[str]
    user_feedback: Optional[str]
    is_replanning: bool
    active_agents: list[str]
    flight_options: Annotated[list, _dedupe_reducer]
    ground_transport_options: Annotated[list, _dedupe_reducer]
    hotel_options: Annotated[list, _dedupe_reducer]
    activity_options: Annotated[list, _dedupe_reducer]
    weather: Optional[dict]
    local_tips: Annotated[list, _dedupe_reducer]
    hidden_gems: Annotated[list, _dedupe_reducer]
    events: Annotated[list, _dedupe_reducer]
    selected_outbound_flight: Optional[dict]
    selected_return_flight: Optional[dict]
    selected_hotel: Optional[dict]
    selected_activities: list[dict]
    budget_tracker: Optional[dict]
    budget_warnings: list[str]
    trip: Optional[dict]
    vibe_score: Optional[dict]
    agent_decisions: Annotated[list, _dedupe_reducer]
    errors: Annotated[list, _dedupe_reducer]
    destination_options: list[dict]
    conversation_response: Optional[str]


def create_initial_state(
    user_id: str = "",
    session_id: str = "",
    raw_query: str = "",
) -> TravelPlannerState:
    """Create initial state with defaults."""
    return TravelPlannerState(
        user_id=user_id,
        session_id=session_id,
        raw_query=raw_query,
        trip_request=None,
        intent_type="plan",
        current_stage="start",
        requires_approval=False,
        approval_type=None,
        user_feedback=None,
        is_replanning=False,
        active_agents=[],
        flight_options=[],
        ground_transport_options=[],
        hotel_options=[],
        activity_options=[],
        weather=None,
        local_tips=[],
        hidden_gems=[],
        events=[],
        selected_outbound_flight=None,
        selected_return_flight=None,
        selected_hotel=None,
        selected_activities=[],
        budget_tracker=None,
        budget_warnings=[],
        trip=None,
        vibe_score=None,
        agent_decisions=[],
        errors=[],
        destination_options=[],
        conversation_response=None,
    )
