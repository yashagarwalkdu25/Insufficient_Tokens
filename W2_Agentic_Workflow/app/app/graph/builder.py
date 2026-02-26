"""
Build the travel planning LangGraph with TRUE parallel fan-out + response validation
and the AI Travel Negotiator (Trade-Off Negotiation Engine).

Architecture:
  supervisor → intent_parser →[conditional]→ destination_recommender → approval_gate
                                           →[Send fan-out]→ flight_search     ─┐
                                                          → hotel_search      ─┤→ search_aggregator →[Send fan-out]→ local_intel    ─┐
                                                          → activity_search   ─┤                                   → festival_check ─┤→ enrichment_aggregator
                                                          → weather_check     ─┘

  enrichment_aggregator → negotiator → feasibility_validator →[passed]→ approval_gate
                                              ↑ (loop back on failure — max 2 retries)

  approval_gate →[conditional]→ budget_optimizer → itinerary_builder → response_validator → vibe_scorer → approval_gate → END

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
from app.graph.nodes.response_validator import validate_response_node
from app.graph.nodes.negotiator import negotiate_bundles_node, feasibility_validator_node


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
    if not sends:
        sends.append(Send("search_aggregator", state))
    return sends


def _fan_out_enrichment(state: dict) -> list[Send]:
    """Dispatch to enrichment agents IN PARALLEL via LangGraph Send."""
    active = state.get("active_agents") or []
    sends: list[Send] = []
    if "local_intel" in active:
        sends.append(Send("local_intel", state))
    sends.append(Send("festival_check", state))
    if not sends:
        sends.append(Send("enrichment_aggregator", state))
    return sends


# ---------------------------------------------------------------------------
# Conditional edge: after intent parsing
# ---------------------------------------------------------------------------

def _route_after_intent(state: dict) -> str:
    """Route: no destination -> recommender; else -> search_dispatcher for parallel fan-out."""
    req = state.get("trip_request") or {}
    dest = (req.get("destination") or "").strip()
    if not dest and not state.get("destination_options"):
        return "destination_recommender"
    if state.get("requires_approval") and state.get("approval_type") == "clarification":
        return "clarification"
    return "search_dispatcher"


# ---------------------------------------------------------------------------
# Conditional edge: after feedback handler (modification requests)
# ---------------------------------------------------------------------------

_SEARCH_AGENTS = {"flight_search", "hotel_search", "activity_search", "weather_check"}
_OPTIMIZATION_AGENTS = {"budget_optimizer", "itinerary_builder", "vibe_scorer"}


def _route_after_feedback(state: dict) -> str:
    """Route after feedback_handler: re-run searches or jump to optimization."""
    active = set(state.get("active_agents") or [])
    if not active:
        return "__end__"
    if active & _SEARCH_AGENTS:
        return "search_dispatcher"
    if active & _OPTIMIZATION_AGENTS:
        return "budget_optimizer"
    return "__end__"


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
    if "enrichment" in stage or "negotiation" in stage or "feasibility" in stage:
        return "budget_optimizer"
    if "vibe" in stage:
        return "__end__"
    return "__end__"


# ---------------------------------------------------------------------------
# Conditional edge: after feasibility validator
# ---------------------------------------------------------------------------

_MAX_NEGOTIATION_RETRIES = 2


def _route_after_feasibility(state: dict) -> str:
    """
    After feasibility_validator:
    - If passed (or max retries reached): proceed to approval_gate.
    - If failed: loop back to negotiator (non-linear loop).
    """
    passed = state.get("feasibility_passed", True)
    if passed:
        return "approval_gate"
    # Count retries via negotiation_log entries starting with "Negotiator started"
    log = state.get("negotiation_log") or []
    retries = sum(1 for line in log if "Negotiator started" in line)
    if retries >= _MAX_NEGOTIATION_RETRIES:
        return "approval_gate"  # give up and proceed
    return "negotiator"


# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------

def build_travel_graph():
    """Build and compile the graph with true parallel fan-out. Sync only."""
    builder = StateGraph(TravelPlannerState)

    # Core nodes
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("intent_parser", parse_intent_node)
    builder.add_node("destination_recommender", recommend_destinations_node)

    # Search agents (run in PARALLEL via Send)
    builder.add_node("search_dispatcher", _search_dispatcher)
    builder.add_node("flight_search", search_flights_node)
    builder.add_node("hotel_search", search_hotels_node)
    builder.add_node("activity_search", search_activities_node)
    builder.add_node("weather_check", check_weather_node)
    builder.add_node("search_aggregator", _search_aggregator)

    # Enrichment agents (run in PARALLEL via Send)
    builder.add_node("enrichment_dispatcher", _enrichment_dispatcher)
    builder.add_node("local_intel", gather_local_intel_node)
    builder.add_node("festival_check", check_festivals_node)
    builder.add_node("enrichment_aggregator", _enrichment_aggregator)

    # Negotiator + Feasibility (between enrichment and optimization)
    builder.add_node("negotiator", negotiate_bundles_node)
    builder.add_node("feasibility_validator", feasibility_validator_node)

    # Optimization & generation pipeline (now includes response_validator)
    builder.add_node("approval_gate", approval_gate_node)
    builder.add_node("budget_optimizer", optimize_budget_node)
    builder.add_node("itinerary_builder", build_itinerary_node)
    builder.add_node("response_validator", validate_response_node)
    builder.add_node("vibe_scorer", score_vibe_node)

    # Terminal handlers
    builder.add_node("feedback_handler", handle_feedback_node)
    builder.add_node("conversation_handler", conversation_handler_node)
    builder.add_node("clarification", clarification_node)

    # EDGES

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

    # Destination recommender -> approval
    builder.add_edge("destination_recommender", "approval_gate")

    # Search dispatcher -> PARALLEL fan-out to search agents via Send()
    builder.add_conditional_edges("search_dispatcher", _fan_out_searches)

    # All search agents converge at search_aggregator
    builder.add_edge("flight_search", "search_aggregator")
    builder.add_edge("hotel_search", "search_aggregator")
    builder.add_edge("activity_search", "search_aggregator")
    builder.add_edge("weather_check", "search_aggregator")

    # Search aggregator -> enrichment dispatcher
    builder.add_edge("search_aggregator", "enrichment_dispatcher")

    # Enrichment dispatcher -> PARALLEL fan-out to enrichment agents via Send()
    builder.add_conditional_edges("enrichment_dispatcher", _fan_out_enrichment)

    # All enrichment agents converge at enrichment_aggregator
    builder.add_edge("local_intel", "enrichment_aggregator")
    builder.add_edge("festival_check", "enrichment_aggregator")

    # Enrichment aggregator -> negotiator (if enabled) or directly to approval_gate
    def _route_after_enrichment(state: dict) -> str:
        return "negotiator" if state.get("use_negotiator", True) else "approval_gate"

    builder.add_conditional_edges("enrichment_aggregator", _route_after_enrichment, {
        "negotiator": "negotiator",
        "approval_gate": "approval_gate",
    })

    # Negotiator -> feasibility validator
    builder.add_edge("negotiator", "feasibility_validator")

    # Feasibility validator -> approval_gate (pass) or back to negotiator (fail, non-linear loop)
    builder.add_conditional_edges("feasibility_validator", _route_after_feasibility, {
        "approval_gate": "approval_gate",
        "negotiator": "negotiator",
    })

    # Approval gate routes
    builder.add_conditional_edges("approval_gate", _route_after_approval, {
        "search_dispatcher": "search_dispatcher",
        "budget_optimizer": "budget_optimizer",
        "__end__": END,
    })

    # Optimization pipeline: budget -> itinerary -> VALIDATE -> vibe -> approval
    builder.add_edge("budget_optimizer", "itinerary_builder")
    builder.add_edge("itinerary_builder", "response_validator")
    builder.add_edge("response_validator", "vibe_scorer")
    builder.add_edge("vibe_scorer", "approval_gate")

    # Feedback handler routes based on which agents need to re-run
    builder.add_conditional_edges("feedback_handler", _route_after_feedback, {
        "search_dispatcher": "search_dispatcher",
        "budget_optimizer": "budget_optimizer",
        "__end__": END,
    })

    # Terminal edges
    builder.add_edge("conversation_handler", END)
    builder.add_edge("clarification", END)

    # Compile
    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)
