"""
Graph runner: run and stream the travel graph; persist state.
Sync only; no asyncio.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Generator, Literal

from app.config import get_settings
from app.graph.state import create_initial_state
from app.graph.builder import build_travel_graph
from app.memory.working_memory import WorkingMemoryManager
from app.memory.conversation_memory import ConversationMemoryManager

logger = logging.getLogger(__name__)


def classify_chat_intent(message: str, has_trip: bool) -> Literal["conversation", "modify", "plan"]:
    """Quick intent classification without invoking the full graph.

    Uses GPT-4o-mini for a single fast call. Falls back to heuristic.
    """
    settings = get_settings()

    if settings.has_openai:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            r = client.chat.completions.create(
                model=settings.GPT4O_MINI_MODEL,
                messages=[
                    {"role": "system", "content": (
                        "Classify the user message into exactly one category. "
                        "Reply with ONLY the single word: conversation, modify, or plan.\n\n"
                        "- conversation: questions, info requests, tips, advice, "
                        "asking about the trip, weather, packing, food, safety, costs, schedule "
                        "(anything that does NOT require changing the itinerary)\n"
                        "- modify: explicit requests to CHANGE something in the plan "
                        "(swap hotel, add activity, make cheaper, remove day, change dates, extend trip)\n"
                        "- plan: requests to create a brand NEW trip from scratch\n\n"
                        f"Context: User {'HAS' if has_trip else 'DOES NOT have'} an existing trip."
                    )},
                    {"role": "user", "content": message},
                ],
                temperature=0,
                max_tokens=10,
            )
            result = (r.choices[0].message.content or "").strip().lower()
            if result in ("conversation", "modify", "plan"):
                return result
        except Exception as exc:
            logger.warning("Quick intent classification failed: %s", exc)

    msg_lower = message.lower()
    plan_signals = ["plan a trip", "new trip", "i want to go", "let's plan", "book a trip"]
    modify_signals = [
        "change", "swap", "replace", "remove", "add more", "make it cheaper",
        "make cheaper", "extend", "shorten", "different hotel", "upgrade",
        "switch", "modify", "update the", "adjust",
    ]
    if any(s in msg_lower for s in plan_signals):
        return "plan"
    if has_trip and any(s in msg_lower for s in modify_signals):
        return "modify"
    return "conversation"


class GraphRunner:
    """Run the compiled graph; persist state to SQLite."""

    def __init__(self):
        self.graph = build_travel_graph()
        self.memory = WorkingMemoryManager()
        self.conv_memory = ConversationMemoryManager()

    def chat(self, message: str, session_id: str) -> str:
        """Handle a conversation message directly without the full graph.

        Calls conversation_handler_node in isolation for fast Q&A.
        Returns the assistant response string.
        """
        logger.info("chat() | session_id=%s msg_len=%s", session_id[:8], len(message))
        state = self.memory.load_state(session_id) or {}
        state["user_feedback"] = message
        state["raw_query"] = message

        self.conv_memory.add_message(session_id, "user", message)

        from app.graph.nodes.conversation_handler import conversation_handler_node
        result = conversation_handler_node(state)
        response = result.get("conversation_response", "")

        if response:
            self.conv_memory.add_message(session_id, "assistant", response)

        logger.info("chat() done | session_id=%s response_len=%s", session_id[:8], len(response))
        return response

    def run(
        self,
        user_input: str,
        session_id: str,
        user_id: str,
        use_negotiator: bool = True,
    ) -> dict[str, Any]:
        """Create initial state, invoke graph, persist and return final state."""
        logger.info("run() | session_id=%s query_len=%s use_negotiator=%s", session_id[:8], len(user_input), use_negotiator)
        config = {"configurable": {"thread_id": session_id}}
        initial = create_initial_state(user_id=user_id, session_id=session_id, raw_query=user_input)
        initial["use_negotiator"] = use_negotiator
        try:
            final = self.graph.invoke(initial, config=config)
            self.memory.save_state(session_id, dict(final))
            logger.info("run() done | session_id=%s has_trip=%s", session_id[:8], bool(final.get("trip")))
            return final
        except Exception as e:
            logger.exception("Graph run failed: %s", e)
            state = dict(initial)
            state["errors"] = state.get("errors", []) + [str(e)]
            self.memory.save_state(session_id, state)
            return state

    def resume(
        self,
        session_id: str,
        user_feedback: str | None = None,
        approval: bool | None = None,
    ) -> dict[str, Any]:
        """Load checkpoint, update state with feedback/approval, resume graph."""
        logger.info("resume() | session_id=%s feedback=%s approval=%s", session_id[:8], bool(user_feedback), approval)
        config = {"configurable": {"thread_id": session_id}}
        try:
            state = self.memory.load_state(session_id)
            if not state:
                logger.warning("resume() no state for session_id=%s", session_id[:8])
                return {}
            if user_feedback:
                state["user_feedback"] = user_feedback
                self.conv_memory.add_message(session_id, "user", user_feedback)
            if approval is not None:
                state["requires_approval"] = False
            final = self.graph.invoke(state, config=config)
            self.memory.save_state(session_id, dict(final))

            if final.get("conversation_response"):
                self.conv_memory.add_message(session_id, "assistant", final["conversation_response"])

            msg_count = len(self.conv_memory.get_recent_messages(session_id, limit=100))
            if msg_count > 0 and msg_count % 5 == 0:
                self.conv_memory.compress_old_messages(session_id)

            logger.info("resume() done | session_id=%s has_trip=%s", session_id[:8], bool(final.get("trip")))
            return final
        except Exception as e:
            logger.exception("Graph resume failed: %s", e)
            return self.memory.load_state(session_id) or {}

    def stream(
        self,
        user_input: str,
        session_id: str,
        user_id: str,
        use_negotiator: bool = True,
    ) -> Generator[tuple[str, dict], None, None]:
        """Stream graph execution; yield (node_name, partial_state) tuples."""
        logger.info("stream() start | session_id=%s query_len=%s use_negotiator=%s", session_id[:8], len(user_input), use_negotiator)
        config = {"configurable": {"thread_id": session_id}}
        initial = create_initial_state(user_id=user_id, session_id=session_id, raw_query=user_input)
        initial["use_negotiator"] = use_negotiator
        node_count = 0
        try:
            for event in self.graph.stream(initial, config=config):
                for node_name, partial_state in event.items():
                    node_count += 1
                    logger.debug("stream node | %s", node_name)
                    yield node_name, partial_state or {}
            snap = self.graph.get_state(config)
            final = getattr(snap, "values", snap) or {}
            self.memory.save_state(session_id, dict(final) if not isinstance(final, dict) else final)

            self.conv_memory.add_message(session_id, "user", user_input)
            if isinstance(final, dict) and final.get("conversation_response"):
                self.conv_memory.add_message(session_id, "assistant", final["conversation_response"])

            logger.info("stream() done | session_id=%s nodes=%s has_trip=%s", session_id[:8], node_count, bool(final.get("trip") if isinstance(final, dict) else False))
        except Exception as e:
            logger.exception("Graph stream failed: %s", e)
            self.memory.save_state(session_id, {**dict(initial), "errors": [str(e)]})
