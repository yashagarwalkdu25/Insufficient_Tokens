"""
Feedback handler agent: LLM-powered modification classification and execution.

Classifies user feedback, determines which agents need to re-run,
and applies the modification context for downstream agents.
Requires OpenAI API key — no keyword fallbacks.
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

    active_agents = ["budget_optimizer", "itinerary_builder", "vibe_scorer"]
    modification_context = feedback

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
  "change_type": "transport_change|hotel_change|budget_change|activity_change|date_change|destination_change|disruption",
  "agents_to_rerun": ["agent1", "agent2"],
  "summary": "brief description of the change",
  "modification_instruction": "clear instruction for the itinerary builder about what to change"
}}

Agent options: flight_search, hotel_search, activity_search, weather_check, local_intel, festival_check, budget_optimizer, itinerary_builder, vibe_scorer

Rules:
- "go by train" / "change to train" → transport_change → [flight_search, budget_optimizer, itinerary_builder, vibe_scorer]
- "make it cheaper" → budget_change → [budget_optimizer, itinerary_builder, vibe_scorer]
- "change hotel" → hotel_change → [hotel_search, budget_optimizer, itinerary_builder, vibe_scorer]
- "more adventure" → activity_change → [activity_search, budget_optimizer, itinerary_builder, vibe_scorer]
- "flight delayed" → disruption → [itinerary_builder, vibe_scorer]
- "different destination" → destination_change → ALL agents
- ALWAYS include itinerary_builder and vibe_scorer in agents_to_rerun"""}],
                temperature=0.2,
            )
            content = (r.choices[0].message.content or "").strip()
            if "```" in content:
                content = content.split("```")[1].replace("json", "").strip()
            data = json.loads(content)
            active_agents = data.get("agents_to_rerun", active_agents)
            modification_context = data.get("modification_instruction", feedback)
            if "itinerary_builder" not in active_agents:
                active_agents.append("itinerary_builder")
            if "vibe_scorer" not in active_agents:
                active_agents.append("vibe_scorer")
            reasoning_parts.append(
                f"LLM classified feedback as '{data.get('change_type', '?')}': "
                f"{data.get('summary', '?')}. Re-running: {active_agents}"
            )
            tokens_used = getattr(r.usage, "total_tokens", 0) if hasattr(r, "usage") else 0
        except Exception as e:
            reasoning_parts.append(
                f"LLM classification failed ({e}); defaulting to budget_optimizer + itinerary_builder + vibe_scorer."
            )
    else:
        if not settings.has_openai:
            reasoning_parts.append("No OpenAI key — cannot classify feedback. Defaulting to rebuild itinerary.")
        else:
            reasoning_parts.append("No feedback provided. Defaulting to rebuild itinerary.")

    latency_ms = int((time.time() - start_t) * 1000)
    decision = {
        "agent_name": "feedback_handler",
        "action": "classify_and_route",
        "reasoning": " ".join(reasoning_parts),
        "result_summary": f"Modification: re-running {len(active_agents)} agents",
        "tokens_used": tokens_used,
        "latency_ms": latency_ms,
    }
    return {
        "is_replanning": True,
        "active_agents": active_agents,
        "current_stage": "handling_feedback",
        "user_feedback": modification_context,
        "agent_decisions": [decision],
    }
