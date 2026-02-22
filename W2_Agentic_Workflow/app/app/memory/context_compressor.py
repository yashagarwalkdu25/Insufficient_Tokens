"""
Context compressor: give each agent only the state fields it needs; estimate tokens.
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)

AGENT_FIELDS: dict[str, list[str]] = {
    "supervisor": ["trip_request", "current_stage", "errors", "raw_query", "user_feedback"],
    "intent_parser": ["raw_query", "conversation_context"],
    "flight_search": ["trip_request"],
    "hotel_search": ["trip_request"],
    "activity_search": ["trip_request"],
    "weather_check": ["trip_request"],
    "local_intel": ["trip_request"],
    "festival_check": ["trip_request"],
    "budget_optimizer": ["flight_options", "ground_transport_options", "hotel_options", "activity_options", "trip_request", "budget_warnings"],
    "itinerary_builder": ["selected_outbound_flight", "selected_return_flight", "selected_hotel", "selected_activities", "weather", "events", "local_tips", "hidden_gems", "trip_request"],
    "vibe_scorer": ["trip", "trip_request"],
    "feedback_handler": ["user_feedback", "trip", "trip_request", "current_stage"],
    "destination_recommender": ["trip_request"],
}


def _summarize_list(items: list[Any], label: str, max_items: int = 3) -> str:
    if not items:
        return f"0 {label}"
    if len(items) <= max_items:
        return f"{len(items)} {label}"
    return f"{len(items)} {label} (e.g. first {max_items} shown)"


class ContextCompressor:
    """Compress state for each agent; estimate tokens with tiktoken."""

    def compress_for_agent(self, state: dict[str, Any], agent_name: str) -> dict[str, Any]:
        """Return state with only fields this agent needs; summarize large lists."""
        fields = AGENT_FIELDS.get(agent_name, list(state.keys()))
        out = {}
        for k in fields:
            if k not in state:
                continue
            v = state[k]
            if isinstance(v, list):
                if k in ("flight_options", "ground_transport_options", "hotel_options", "activity_options"):
                    if v and isinstance(v[0], dict):
                        prices = [x.get("total_price") or x.get("price") for x in v if isinstance(x, dict)]
                        out[k] = _summarize_list(v, k) + (f" (e.g. ₹{min(p for p in prices if p)}-₹{max(p for p in prices if p)})" if prices else "")
                    else:
                        out[k] = _summarize_list(v, k)
                else:
                    out[k] = v[:5] if len(v) > 5 else v
            else:
                out[k] = v
        return out

    def estimate_tokens(self, text: str) -> int:
        """Token count using tiktoken cl100k_base."""
        try:
            import tiktoken
            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except Exception:
            return len(text) // 4
