"""
Conditional edge functions for the travel planning graph.
"""
from typing import Literal


def route_after_supervisor(state: dict) -> Literal["intent_parser", "feedback_handler", "conversation_handler"]:
    """Route based on intent_type from supervisor."""
    intent = (state.get("intent_type") or "plan").lower()
    if intent == "modify":
        return "feedback_handler"
    if intent == "conversation":
        return "conversation_handler"
    return "intent_parser"
