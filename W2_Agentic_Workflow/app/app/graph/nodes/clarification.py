"""Clarification: ask user for missing info. Stub."""
from typing import Any


def clarification_node(state: dict[str, Any]) -> dict[str, Any]:
    """Set requires_approval for clarification."""
    return {"requires_approval": True, "approval_type": "clarification", "current_stage": "clarification"}
