"""Planning progress: live timeline with agent steps and previews."""
from __future__ import annotations

import streamlit as st
from typing import Generator, Any


AGENT_LABELS = {
    "supervisor":              ("🧭", "Routing your request"),
    "intent_parser":           ("📝", "Understanding your trip"),
    "destination_recommender": ("📍", "Recommending destinations"),
    "search_dispatcher":       ("🚀", "Dispatching search agents"),
    "flight_search":           ("✈️",  "Finding flights & transport"),
    "hotel_search":            ("🏡", "Scouting stays"),
    "activity_search":         ("🎭", "Discovering experiences"),
    "weather_check":           ("☁️",  "Checking weather"),
    "search_aggregator":       ("📦", "Merging search results"),
    "enrichment_dispatcher":   ("🔮", "Dispatching enrichment"),
    "local_intel":             ("🗣️", "Gathering local secrets"),
    "festival_check":          ("🪔", "Checking festivals & events"),
    "enrichment_aggregator":   ("📦", "Merging enrichment"),
    "approval_gate":           ("⏸️",  "Approval checkpoint"),
    "budget_optimizer":        ("💰", "Optimizing your budget"),
    "itinerary_builder":       ("📖", "Crafting your itinerary"),
    "response_validator":      ("🛡️", "Validating & fact-checking"),
    "vibe_scorer":             ("🎯", "Scoring trip vibe"),
}

_SKIP_DISPLAY = {"search_dispatcher", "search_aggregator", "enrichment_dispatcher", "enrichment_aggregator"}


def _preview_text(node_name: str, partial_state: dict[str, Any]) -> str:
    if node_name == "supervisor":
        return f"Intent: {partial_state.get('intent_type', 'plan')}"
    if node_name == "intent_parser":
        req = partial_state.get("trip_request") or {}
        return f"{req.get('destination', '—')} · ₹{req.get('budget', '—')}"
    if node_name == "flight_search":
        f = len(partial_state.get("flight_options") or [])
        g = len(partial_state.get("ground_transport_options") or [])
        return f"{f} flights, {g} ground options"
    if node_name == "hotel_search":
        return f"{len(partial_state.get('hotel_options') or [])} stays found"
    if node_name == "activity_search":
        return f"{len(partial_state.get('activity_options') or [])} experiences"
    if node_name == "weather_check":
        w = partial_state.get("weather") or {}
        if isinstance(w, dict):
            summary = w.get("summary", "")
            if summary:
                # Count days in summary (pipe-separated entries)
                n_days = len([p for p in summary.split("|") if p.strip()])
                # Show first entry only as a teaser
                first = summary.split("|")[0].strip()
                # Trim to ~40 chars
                if len(first) > 42:
                    first = first[:40] + "…"
                return f"{first}" + (f" +{n_days-1} more" if n_days > 1 else "")
            return "Forecast ready"
        return "Done"
    if node_name == "local_intel":
        t = len(partial_state.get("local_tips") or [])
        g = len(partial_state.get("hidden_gems") or [])
        return f"{t} tips, {g} hidden gems"
    if node_name == "festival_check":
        return f"{len(partial_state.get('events') or [])} events found"
    if node_name == "budget_optimizer":
        tracker = partial_state.get("budget_tracker") or {}
        return f"₹{tracker.get('total_budget', 0):,.0f} optimized" if tracker else "Selections made"
    if node_name == "itinerary_builder":
        trip = partial_state.get("trip") or {}
        days = len(trip.get("days") or [])
        return f"{days} days · ₹{trip.get('total_cost', 0):,.0f}"
    if node_name == "response_validator":
        issues = partial_state.get("validation_issues") or []
        if issues:
            return f"{len(issues)} items flagged for review"
        return "All items verified"
    if node_name == "vibe_scorer":
        vs = partial_state.get("vibe_score") or {}
        return f"{vs.get('overall_score', '—')}/100 — {vs.get('tagline', '')}"
    if node_name == "approval_gate":
        stage = partial_state.get("current_stage", "")
        return "Trip complete!" if "trip_complete" in stage else "Checkpoint passed"
    return "Done"


def render_planning_progress(stream_generator: Generator[tuple[str, dict], None, None] | None) -> bool:
    """Render live timeline. Returns True when stream completes."""
    if stream_generator is None:
        st.info("Preparing your journey...")
        return False

    st.markdown("### Crafting your journey...")
    st.caption("TripSaathi agents are working together to find the best options for you.")
    progress_bar = st.progress(0, text="Starting up...")

    visible_agents = [k for k in AGENT_LABELS if k not in _SKIP_DISPLAY]
    agent_slots: dict[str, st.delta_generator.DeltaGenerator] = {}
    for name in visible_agents:
        agent_slots[name] = st.empty()

    status_area = st.empty()
    final_state = {}
    completed = []
    previews: dict[str, str] = {}
    error_occurred = False
    total_expected = len(visible_agents)

    try:
        for node_name, partial_state in stream_generator:
            final_state.update(partial_state or {})
            if node_name not in completed:
                completed.append(node_name)
            preview = _preview_text(node_name, partial_state or {})
            previews[node_name] = preview

            visible_done = [n for n in completed if n not in _SKIP_DISPLAY]
            pct = min(len(visible_done) / max(total_expected, 1), 1.0)
            icon, label = AGENT_LABELS.get(node_name, ("⚙️", node_name))
            progress_bar.progress(pct, text=f"{icon} {label}...")

            for agent_name in visible_agents:
                slot = agent_slots[agent_name]
                a_icon, a_label = AGENT_LABELS[agent_name]
                if agent_name in completed:
                    prev = previews.get(agent_name, "Done")
                    slot.markdown(
                        f'<div class="ts-timeline-item ts-timeline-done">'
                        f'{a_icon} <strong>{a_label}</strong> &nbsp;—&nbsp; {prev}</div>',
                        unsafe_allow_html=True,
                    )
                elif _is_likely_running(agent_name, completed):
                    slot.markdown(
                        f'<div class="ts-timeline-item ts-timeline-active">'
                        f'{a_icon} <strong>{a_label}</strong> &nbsp;—&nbsp; running...</div>',
                        unsafe_allow_html=True,
                    )
    except Exception as e:
        error_occurred = True
        status_area.error(f"Planning error: {e}")

    progress_bar.progress(1.0, text="Journey crafted!")

    for agent_name in visible_agents:
        slot = agent_slots[agent_name]
        a_icon, a_label = AGENT_LABELS[agent_name]
        if agent_name in completed:
            prev = previews.get(agent_name, "Done")
            slot.markdown(
                f'<div class="ts-timeline-item ts-timeline-done">'
                f'{a_icon} <strong>{a_label}</strong> &nbsp;—&nbsp; {prev}</div>',
                unsafe_allow_html=True,
            )
        else:
            slot.empty()

    st.session_state["planning_completed_nodes"] = completed
    st.session_state["planning_previews"] = previews
    st.session_state["planning_done"] = True
    st.session_state["planning_final_state"] = final_state

    if not error_occurred:
        status_area.success("All agents completed! Your trip is ready.")

    return True


def _is_likely_running(agent_name: str, completed: list[str]) -> bool:
    search_agents = {"flight_search", "hotel_search", "activity_search", "weather_check"}
    if agent_name in search_agents and "search_dispatcher" in completed and agent_name not in completed:
        if any(sa in completed for sa in search_agents):
            return True
    enrich_agents = {"local_intel", "festival_check"}
    if agent_name in enrich_agents and "enrichment_dispatcher" in completed and agent_name not in completed:
        if any(ea in completed for ea in enrich_agents):
            return True
    return False
