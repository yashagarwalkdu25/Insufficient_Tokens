"""Approval gate: manage HITL checkpoints. No LLM."""
from typing import Any


def approval_gate_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    HITL checkpoint. When resuming (requires_approval already False), pass through.
    Otherwise, determine what kind of approval to request.
    """
    # If approval has been cleared (user approved), continue the pipeline
    if state.get("requires_approval") is False:
        stage = state.get("current_stage", "")
        # After enrichment → continue to budget optimizer
        if "enrichment" in stage:
            return {"current_stage": "enrichment_approved"}
        # After vibe scoring → trip complete
        if "vibe" in stage:
            return {"current_stage": "trip_complete", "requires_approval": True, "approval_type": "itinerary"}
        # After destination → continue to search
        if "destination" in stage:
            return {"current_stage": "destination_approved"}
        return {}

    # Determine approval type
    stage = state.get("current_stage", "")
    if "destination" in stage or state.get("destination_options"):
        approval_type = "destination"
    elif state.get("trip") and state.get("vibe_score"):
        approval_type = "itinerary"
    else:
        approval_type = "research"

    return {
        "requires_approval": True,
        "approval_type": approval_type,
        "current_stage": "awaiting_approval",
    }
