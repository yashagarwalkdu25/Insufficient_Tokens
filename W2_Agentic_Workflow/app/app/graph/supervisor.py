"""
Supervisor node: classify intent and set active_agents.
Uses GPT-4o-mini; logs AgentDecision.
"""
import json
import logging
import time
from typing import Any

from app.config import get_settings
from app.prompts.supervisor import SYSTEM_PROMPT, USER_TEMPLATE

logger = logging.getLogger(__name__)


def supervisor_node(state: dict[str, Any]) -> dict[str, Any]:
    """Classify intent and set active_agents; return partial state update."""
    message = (state.get("user_feedback") or state.get("raw_query") or "").strip()
    current_stage = state.get("current_stage", "start")
    has_trip = bool(state.get("trip"))
    settings = get_settings()
    
    intent_type = "plan"
    active_agents = [
        "intent_parser",
        "flight_search",
        "hotel_search",
        "activity_search",
        "weather_check",
        "local_intel",
        "festival_check",
        "budget_optimizer",
        "itinerary_builder",
        "vibe_scorer",
    ]
    reasoning = "Default plan intent with all agents"
    
    if settings.has_openai:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            start = time.time()
            
            # Add context about whether they have a trip already
            context_note = f"\nContext: User {'HAS' if has_trip else 'DOES NOT HAVE'} an existing trip plan."
            
            r = client.chat.completions.create(
                model=settings.GPT4O_MINI_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT + context_note},
                    {"role": "user", "content": USER_TEMPLATE.format(current_stage=current_stage, message=message)},
                ],
                temperature=0.2,  # Lower temperature for more consistent routing
            )
            latency_ms = int((time.time() - start) * 1000)
            content = (r.choices[0].message.content or "").strip()
            if content:
                # Strip markdown code fences
                if "```" in content:
                    parts = content.split("```")
                    content = parts[1] if len(parts) > 1 else parts[0]
                    content = content.removeprefix("json").strip()
                # Find JSON object in the response
                start_idx = content.find("{")
                end_idx = content.rfind("}")
                if start_idx != -1 and end_idx != -1:
                    content = content[start_idx:end_idx + 1]
                data = json.loads(content)
                intent_type = data.get("intent_type", "plan")
                active_agents = data.get("active_agents", active_agents)
                reasoning = data.get("reasoning", f"LLM classified as {intent_type}")
            tok = r.usage.total_tokens if getattr(r, "usage", None) else 0
            decision = {
                "agent_name": "supervisor",
                "action": "classify_intent",
                "reasoning": reasoning,
                "result_summary": f"{intent_type} → {len(active_agents)} agents",
                "tokens_used": tok,
                "latency_ms": latency_ms,
            }
        except Exception as e:
            logger.warning("Supervisor LLM failed: %s", e)
            # Heuristic fallback
            msg_lower = message.lower()
            if has_trip and any(q in msg_lower for q in ["what", "when", "where", "how much", "tell me", "show me", "?"]):
                intent_type = "conversation"
                active_agents = []
                reasoning = f"Heuristic: Question detected with existing trip → conversation"
            elif has_trip and any(w in msg_lower for w in ["change", "modify", "update", "cheaper", "different", "remove", "add more"]):
                intent_type = "modify"
                active_agents = []
                reasoning = f"Heuristic: Modification keywords detected → modify"
            else:
                intent_type = "plan"
                reasoning = f"Heuristic fallback → plan (LLM error: {str(e)[:50]})"
            
            decision = {
                "agent_name": "supervisor",
                "action": "classify_intent",
                "reasoning": reasoning,
                "result_summary": f"{intent_type}",
                "tokens_used": 0,
                "latency_ms": 0,
            }
    else:
        # No OpenAI - use simple heuristics
        msg_lower = message.lower()
        if has_trip and any(q in msg_lower for q in ["what", "when", "where", "how much", "tell me", "?"]):
            intent_type = "conversation"
            active_agents = []
        elif has_trip and any(w in msg_lower for w in ["change", "modify", "cheaper", "different"]):
            intent_type = "modify"
            active_agents = []
        
        decision = {
            "agent_name": "supervisor",
            "action": "classify_intent",
            "reasoning": "No OpenAI key; using heuristics",
            "result_summary": intent_type,
            "tokens_used": 0,
            "latency_ms": 0,
        }

    return {
        "intent_type": intent_type,
        "active_agents": active_agents,
        "current_stage": "supervisor_done",
        "agent_decisions": [decision],
    }
