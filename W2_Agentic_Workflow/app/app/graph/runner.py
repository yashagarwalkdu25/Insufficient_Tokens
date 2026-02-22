"""
Graph runner: run and stream the travel graph; persist state.
Sync only; no asyncio.
"""
from __future__ import annotations

import logging
from typing import Any, Generator

from app.graph.state import create_initial_state
from app.graph.builder import build_travel_graph
from app.memory.working_memory import WorkingMemoryManager

logger = logging.getLogger(__name__)


class GraphRunner:
    """Run the compiled graph; persist state to SQLite."""

    def __init__(self):
        self.graph = build_travel_graph()
        self.memory = WorkingMemoryManager()

    def run(
        self,
        user_input: str,
        session_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        """Create initial state, invoke graph, persist and return final state."""
        logger.info("run() | session_id=%s query_len=%s", session_id[:8], len(user_input))
        config = {"configurable": {"thread_id": session_id}}
        initial = create_initial_state(user_id=user_id, session_id=session_id, raw_query=user_input)
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
            if approval is not None:
                state["requires_approval"] = False
            final = self.graph.invoke(state, config=config)
            self.memory.save_state(session_id, dict(final))
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
    ) -> Generator[tuple[str, dict], None, None]:
        """Stream graph execution; yield (node_name, partial_state) tuples."""
        logger.info("stream() start | session_id=%s query_len=%s", session_id[:8], len(user_input))
        config = {"configurable": {"thread_id": session_id}}
        initial = create_initial_state(user_id=user_id, session_id=session_id, raw_query=user_input)
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
            logger.info("stream() done | session_id=%s nodes=%s has_trip=%s", session_id[:8], node_count, bool(final.get("trip") if isinstance(final, dict) else False))
        except Exception as e:
            logger.exception("Graph stream failed: %s", e)
            self.memory.save_state(session_id, {**dict(initial), "errors": [str(e)]})
