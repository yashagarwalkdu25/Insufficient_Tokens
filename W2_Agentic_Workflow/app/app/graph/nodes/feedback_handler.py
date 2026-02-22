"""
Feedback handler agent: LLM-powered modification classification.

Classifies user feedback and determines which agents need to re-run.
"""
import json
import logging
import time
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)


def handle_feedback_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: classify modification feedback and set re-planning agents."""
    start_t = time.time()
    feedback = (state.get("user_feedback") or "").strip()
    reasoning_parts: list[str] = []
    tokens_used = 0

    # Default agents to re-run
    active_agents = ["budget_optimizer", "itinerary_builder", "vibe_scorer"]

    settings = get_settings()
    if settings.has_openai and feedback:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            r = client.chat.completions.create(
                model=settings.GPT4O_MINI_MODEL,
                messages=[{"role": "user", "content": f"""Classify this travel plan modification request and determine which agents need to re-run.

Feedback: "{feedback}"

Return JSON:
{{
  "change_type": "hotel_change|budget_change|activity_change|date_change|destination_change|disruption",
  "agents_to_rerun": ["agent1", "agent2"],
  "summary": "brief description of the change"
}}

Agent options: flight_search, hotel_search, activity_search, weather_check, local_intel, festival_check, budget_optimizer, itinerary_builder, vibe_scorer

Rules:
- "make it cheaper" → budget_change → [budget_optimizer, itinerary_builder, vibe_scorer]
- "change hotel" → hotel_change → [hotel_search, budget_optimizer, itinerary_builder, vibe_scorer]
- "more adventure" → activity_change → [activity_search, budget_optimizer, itinerary_builder, vibe_scorer]
- "flight delayed" → disruption → [itinerary_builder, vibe_scorer]
- "different destination" → destination_change → ALL agents"""}],
                temperature=0.2,
            )
            content = (r.choices[0].message.content or "").strip()
            if "```" in content:
                content = content.split("```")[1].replace("json", "").strip()
            data = json.loads(content)
            active_agents = data.get("agents_to_rerun", active_agents)
            reasoning_parts.append(f"LLM classified feedback as '{data.get('change_type', '?')}': {data.get('summary', '?')}. Re-running: {active_agents}")
            tokens_used = getattr(r.usage, "total_tokens", 0) if hasattr(r, "usage") else 0
        except Exception as e:
            reasoning_parts.append(f"LLM classification failed ({e}); using keyword-based fallback.")
    else:
        reasoning_parts.append("Using keyword-based feedback classification.")

    # ── Keyword fallback ───────────────────────────────────────────────────
    if not reasoning_parts or "keyword" in reasoning_parts[-1]:
        fl = feedback.lower()
        if any(w in fl for w in ("hotel", "stay", "accommodation")):
            active_agents = ["hotel_search", "budget_optimizer", "itinerary_builder", "vibe_scorer"]
        elif any(w in fl for w in ("flight", "transport", "bus", "train")):
            active_agents = ["flight_search", "budget_optimizer", "itinerary_builder", "vibe_scorer"]
        elif any(w in fl for w in ("activity", "adventure", "more", "add")):
            active_agents = ["activity_search", "budget_optimizer", "itinerary_builder", "vibe_scorer"]
        elif any(w in fl for w in ("budget", "cheap", "expensive", "cost")):
            active_agents = ["budget_optimizer", "itinerary_builder", "vibe_scorer"]
        elif any(w in fl for w in ("delay", "cancel", "disrupt")):
            active_agents = ["itinerary_builder", "vibe_scorer"]
        reasoning_parts.append(f"Keyword match → re-run: {active_agents}")

    latency_ms = int((time.time() - start_t) * 1000)
    decision = {
        "agent_name": "feedback_handler",
        "action": "classify",
        "reasoning": " ".join(reasoning_parts),
        "result_summary": f"Modification: re-running {len(active_agents)} agents",
        "tokens_used": tokens_used,
        "latency_ms": latency_ms,
    }
    return {
        "is_replanning": True,
        "active_agents": active_agents,
        "current_stage": "handling_feedback",
        "agent_decisions": [decision],
    }
