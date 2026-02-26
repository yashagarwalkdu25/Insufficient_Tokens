"""
Build the travel planning LangGraph with TRUE parallel fan-out.

Architecture:
  supervisor → intent_parser →[conditional]→ destination_recommender → approval_gate
                                           →[Send fan-out]→ flight_search     ─┐
                                                          → hotel_search      ─┤→ search_aggregator →[Send fan-out]→ local_intel    ─┐
                                                          → activity_search   ─┤                                   → festival_check ─┤→ enrichment_aggregator → approval_gate
                                                          → weather_check     ─┘

  approval_gate →[conditional]→ budget_optimizer → itinerary_builder → vibe_scorer → approval_gate → END

  feedback_handler / conversation_handler / clarification → END

Sync only; MemorySaver checkpointer.
"""
from __future__ import annotations

from typing import List, Literal, Sequence, Union

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Send

from app.graph.state import TravelPlannerState, create_initial_state
from app.graph.supervisor import supervisor_node
from app.graph.edges import route_after_supervisor
from app.graph.nodes.intent_parser import parse_intent_node
from app.graph.nodes.destination_recommender import recommend_destinations_node
from app.graph.nodes.flight_search import search_flights_node
from app.graph.nodes.hotel_search import search_hotels_node
from app.graph.nodes.activity_search import search_activities_node
from app.graph.nodes.weather_check import check_weather_node
from app.graph.nodes.local_intel import gather_local_intel_node
from app.graph.nodes.festival_check import check_festivals_node
from app.graph.nodes.approval_gate import approval_gate_node
from app.graph.nodes.feedback_handler import handle_feedback_node
from app.graph.nodes.conversation_handler import conversation_handler_node
from app.graph.nodes.clarification import clarification_node
from app.graph.nodes.budget_optimizer import optimize_budget_node
from app.graph.nodes.itinerary_builder import build_itinerary_node
from app.graph.nodes.vibe_scorer import score_vibe_node


# ---------------------------------------------------------------------------
# Lightweight dispatcher / aggregator nodes
# ---------------------------------------------------------------------------

def _search_dispatcher(state: dict) -> dict:
    """Pass-through node that marks the start of parallel search."""
    return {"current_stage": "searching"}


def _search_aggregator(state: dict) -> dict:
    """Pass-through after all parallel searches complete. State is already merged."""
    return {"current_stage": "search_done"}


def _enrichment_dispatcher(state: dict) -> dict:
    """Pass-through to start parallel enrichment."""
    return {"current_stage": "enriching"}


def _enrichment_aggregator(state: dict) -> dict:
    """Pass-through after all enrichment agents complete. State is already merged."""
    return {"current_stage": "enrichment_done"}


# ---------------------------------------------------------------------------
# Fan-out routing functions (return Send objects for parallel execution)
# ---------------------------------------------------------------------------

def _fan_out_searches(state: dict) -> list[Send]:
    """Dispatch to all active search agents IN PARALLEL via LangGraph Send."""
    active = state.get("active_agents") or []
    sends: list[Send] = []
    for agent_name in ["flight_search", "hotel_search", "activity_search", "weather_check"]:
        if agent_name in active:
            sends.append(Send(agent_name, state))
    # If no search agents active, skip to aggregator directly
    if not sends:
        sends.append(Send("search_aggregator", state))
    return sends


def _fan_out_enrichment(state: dict) -> list[Send]:
    """Dispatch to enrichment agents IN PARALLEL via LangGraph Send."""
    active = state.get("active_agents") or []
    sends: list[Send] = []
    if "local_intel" in active:
        sends.append(Send("local_intel", state))
    sends.append(Send("festival_check", state))  # Always run festival check
    if not sends:
        sends.append(Send("enrichment_aggregator", state))
    return sends


# ---------------------------------------------------------------------------
# Conditional edge: after intent parsing
# ---------------------------------------------------------------------------

def _route_after_intent(state: dict) -> str:
    """Route: no destination → recommender; else → search_dispatcher for parallel fan-out."""
    req = state.get("trip_request") or {}
    dest = (req.get("destination") or "").strip()
    if not dest and not state.get("destination_options"):
        return "destination_recommender"
    if state.get("requires_approval") and state.get("approval_type") == "clarification":
        return "clarification"
    return "search_dispatcher"


# ---------------------------------------------------------------------------
# Conditional edge: after approval gate
# ---------------------------------------------------------------------------

def _route_after_approval(state: dict) -> str:
    """After approval_gate: where to go."""
    if state.get("requires_approval"):
        return "__end__"
    stage = state.get("current_stage", "")
    if "dest" in stage or "destination" in stage:
        return "search_dispatcher"
    if "enrichment" in stage:
        return "budget_optimizer"
    # If vibe_scored, we're done
    if "vibe" in stage:
        return "__end__"
    return "__end__"


# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------

def build_travel_graph():
    """Build and compile the graph with true parallel fan-out. Sync only."""
    builder = StateGraph(TravelPlannerState)

    # ── Core nodes ─────────────────────────────────────────────────────────
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("intent_parser", parse_intent_node)
    builder.add_node("destination_recommender", recommend_destinations_node)

    # ── Search agents (run in PARALLEL via Send) ───────────────────────────
    builder.add_node("search_dispatcher", _search_dispatcher)
    builder.add_node("flight_search", search_flights_node)
    builder.add_node("hotel_search", search_hotels_node)
    builder.add_node("activity_search", search_activities_node)
    builder.add_node("weather_check", check_weather_node)
    builder.add_node("search_aggregator", _search_aggregator)

    # ── Enrichment agents (run in PARALLEL via Send) ───────────────────────
    builder.add_node("enrichment_dispatcher", _enrichment_dispatcher)
    builder.add_node("local_intel", gather_local_intel_node)
    builder.add_node("festival_check", check_festivals_node)
    builder.add_node("enrichment_aggregator", _enrichment_aggregator)

    # ── Optimization & generation pipeline ─────────────────────────────────
    builder.add_node("approval_gate", approval_gate_node)
    builder.add_node("budget_optimizer", optimize_budget_node)
    builder.add_node("itinerary_builder", build_itinerary_node)
    builder.add_node("vibe_scorer", score_vibe_node)

    # ── Terminal handlers ──────────────────────────────────────────────────
    builder.add_node("feedback_handler", handle_feedback_node)
    builder.add_node("conversation_handler", conversation_handler_node)
    builder.add_node("clarification", clarification_node)

    # ── EDGES ──────────────────────────────────────────────────────────────

    # Entry
    builder.set_entry_point("supervisor")

    # Supervisor routes by intent
    builder.add_conditional_edges("supervisor", route_after_supervisor, {
        "intent_parser": "intent_parser",
        "feedback_handler": "feedback_handler",
        "conversation_handler": "conversation_handler",
    })

    # Intent parser routes
    builder.add_conditional_edges("intent_parser", _route_after_intent, {
        "destination_recommender": "destination_recommender",
        "search_dispatcher": "search_dispatcher",
        "clarification": "clarification",
    })

    # Destination recommender → approval
    builder.add_edge("destination_recommender", "approval_gate")

    # Search dispatcher → PARALLEL fan-out to search agents via Send()
    builder.add_conditional_edges("search_dispatcher", _fan_out_searches)

    # All search agents converge at search_aggregator (LangGraph waits for ALL)
    builder.add_edge("flight_search", "search_aggregator")
    builder.add_edge("hotel_search", "search_aggregator")
    builder.add_edge("activity_search", "search_aggregator")
    builder.add_edge("weather_check", "search_aggregator")

    # Search aggregator → enrichment dispatcher
    builder.add_edge("search_aggregator", "enrichment_dispatcher")

    # Enrichment dispatcher → PARALLEL fan-out to enrichment agents via Send()
    builder.add_conditional_edges("enrichment_dispatcher", _fan_out_enrichment)

    # All enrichment agents converge at enrichment_aggregator
    builder.add_edge("local_intel", "enrichment_aggregator")
    builder.add_edge("festival_check", "enrichment_aggregator")

    # Enrichment aggregator → approval gate
    builder.add_edge("enrichment_aggregator", "approval_gate")

    # Approval gate routes
    builder.add_conditional_edges("approval_gate", _route_after_approval, {
        "search_dispatcher": "search_dispatcher",
        "budget_optimizer": "budget_optimizer",
        "__end__": END,
    })

    # Optimization pipeline (sequential — each depends on previous)
    builder.add_edge("budget_optimizer", "itinerary_builder")
    builder.add_edge("itinerary_builder", "vibe_scorer")
    builder.add_edge("vibe_scorer", "approval_gate")

    # Terminal edges
    builder.add_edge("feedback_handler", END)
    builder.add_edge("conversation_handler", END)
    builder.add_edge("clarification", END)

    # Compile
    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)
