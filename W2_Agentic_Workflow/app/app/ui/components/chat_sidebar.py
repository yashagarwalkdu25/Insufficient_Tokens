"""Chat sidebar: interactive trip chat with intelligent routing.

Conversation questions are handled instantly via LLM.
Modification requests trigger the graph pipeline.
New plan requests trigger full replanning.
"""
from __future__ import annotations

import logging

import streamlit as st

logger = logging.getLogger(__name__)


def render_chat_sidebar() -> None:
    if not st.session_state.get("show_modify_sidebar"):
        return

    with st.sidebar:
        h_col, close_col = st.columns([0.85, 0.15])
        with h_col:
            st.markdown(
                '<h3 style="margin:0; font-size:1.15rem; color:#1A5653;">TripSaathi Chat</h3>',
                unsafe_allow_html=True,
            )
        with close_col:
            if st.button("✕", key="close_chat_panel", help="Close chat panel"):
                st.session_state["show_modify_sidebar"] = False
                st.session_state["modify_chat_active"] = False
                st.rerun()

        trip_state = st.session_state.get("trip_state") or {}
        trip = trip_state.get("trip")
        if trip:
            dest = trip.get("destination", "?")
            start_d = trip.get("start_date", "?")
            end_d = trip.get("end_date", "?")
            total = trip.get("total_cost", 0)
            st.markdown(
                f'<div style="background:#F0F7F6; border-radius:8px; padding:0.5rem 0.7rem; margin-bottom:0.6rem;">'
                f'<span style="font-weight:600; color:#1A5653;">{dest}</span>'
                f'<br/><span style="font-size:0.78rem; color:#7A8B8A;">{start_d} → {end_d} · ₹{total:,.0f}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.markdown(
            '<p style="font-size:0.8rem; color:#7A8B8A; margin:0 0 0.5rem 0;">'
            'Ask me anything about your trip, request changes, or let me suggest improvements.</p>',
            unsafe_allow_html=True,
        )

        if "chat_messages" not in st.session_state:
            st.session_state["chat_messages"] = []

        messages = st.session_state["chat_messages"]

        if not messages and trip:
            welcome = (
                f"Hey! I'm TripSaathi, your travel buddy. 🌿\n\n"
                f"I've planned your trip to **{trip.get('destination', 'your destination')}**. "
                f"Feel free to ask me anything — want to swap activities, adjust the budget, "
                f"change dates, or get local tips? Just ask!"
            )
            messages.append({"role": "assistant", "content": welcome})
            st.session_state["chat_messages"] = messages

        conv_response = trip_state.get("conversation_response")
        if conv_response and not any(m.get("content") == conv_response for m in messages):
            messages.append({"role": "assistant", "content": conv_response})
            st.session_state["chat_messages"] = messages

        chat_container = st.container(height=380)
        with chat_container:
            for m in messages:
                role = m.get("role", "user")
                content = m.get("content", "")
                with st.chat_message(role):
                    st.markdown(content)

        warnings = trip_state.get("budget_warnings") or []
        issues = trip_state.get("validation_issues") or []
        if issues:
            with st.expander("Validation notes", expanded=False):
                for issue in issues[:5]:
                    if isinstance(issue, dict):
                        severity = issue.get("severity", "info")
                        icon = "⚠️" if severity == "warning" else "ℹ️"
                        st.caption(f"{icon} {issue.get('message', '')}")
                    else:
                        st.caption(f"ℹ️ {issue}")

        st.markdown('<div style="height:4px;"></div>', unsafe_allow_html=True)

        st.caption("Quick actions")
        _render_quick_actions(trip)

        st.markdown('<div style="height:6px;"></div>', unsafe_allow_html=True)

        feedback = st.chat_input("Ask anything about your trip...")
        if feedback:
            _handle_message(feedback)


def _render_quick_actions(trip: dict | None) -> None:
    if not trip:
        q1, q2 = st.columns(2)
        with q1:
            if st.button("Plan a trip", key="q_plan", use_container_width=True):
                _handle_message("Help me plan a new trip")
        with q2:
            if st.button("Suggest places", key="q_suggest", use_container_width=True):
                _handle_message("Suggest some good travel destinations in India")
        return

    total_cost = trip.get("total_cost", 0)

    row1_c1, row1_c2 = st.columns(2)
    with row1_c1:
        if st.button("Make cheaper", key="q_cheap", use_container_width=True):
            _trigger_modify(
                f"The current trip costs ₹{total_cost:,.0f}. Can you suggest ways to reduce the budget? "
                "Show me specific items I can cut or cheaper alternatives."
            )
    with row1_c2:
        if st.button("More adventure", key="q_adv", use_container_width=True):
            _trigger_modify("Add more adventure and outdoor activities to my itinerary. What options are available?")

    row2_c1, row2_c2 = st.columns(2)
    with row2_c1:
        if st.button("Change hotel", key="q_hotel", use_container_width=True):
            _trigger_modify("Show me different hotel options. What are my alternatives in terms of price and location?")
    with row2_c2:
        if st.button("Food spots", key="q_food", use_container_width=True):
            _handle_message("Recommend the best local food spots and must-try dishes at my destination.")

    row3_c1, row3_c2 = st.columns(2)
    with row3_c1:
        if st.button("What to pack", key="q_pack", use_container_width=True):
            _handle_message("What should I pack for this trip? Consider the weather and activities planned.")
    with row3_c2:
        if st.button("Safety tips", key="q_safety", use_container_width=True):
            _handle_message("What are the safety tips and things to be careful about at my destination?")


def _handle_message(message: str) -> None:
    """Intelligently route the message: conversation vs modify vs plan."""
    from app.graph.runner import classify_chat_intent, GraphRunner

    msgs = st.session_state.get("chat_messages") or []
    msgs.append({"role": "user", "content": message})
    st.session_state["chat_messages"] = msgs

    has_trip = bool((st.session_state.get("trip_state") or {}).get("trip"))
    intent = classify_chat_intent(message, has_trip)
    logger.info("Chat intent: %s for message: %s", intent, message[:80])

    if intent == "conversation":
        _handle_conversation(message)
    elif intent == "modify":
        _trigger_modify(message)
    else:
        _trigger_plan(message)


def _handle_conversation(message: str) -> None:
    """Handle conversation/Q&A directly without triggering the graph."""
    from app.graph.runner import GraphRunner

    session_id = st.session_state.get("session_id", "")

    with st.sidebar:
        with st.spinner("Thinking..."):
            runner = GraphRunner()
            response = runner.chat(message, session_id)

    if response:
        msgs = st.session_state.get("chat_messages") or []
        msgs.append({"role": "assistant", "content": response})
        st.session_state["chat_messages"] = msgs
    else:
        msgs = st.session_state.get("chat_messages") or []
        msgs.append({"role": "assistant", "content": "I couldn't process that. Could you rephrase?"})
        st.session_state["chat_messages"] = msgs

    st.rerun()


def _trigger_modify(message: str) -> None:
    """Trigger the graph pipeline for modification requests."""
    msgs = st.session_state.get("chat_messages") or []
    if not any(m.get("content") == message for m in msgs):
        msgs.append({"role": "user", "content": message})
        st.session_state["chat_messages"] = msgs

    st.session_state["current_screen"] = "planning"
    st.session_state["plan_query"] = None
    st.session_state["planning_resume_feedback"] = message
    st.rerun()


def _trigger_plan(message: str) -> None:
    """Trigger full replanning for new trip requests."""
    msgs = st.session_state.get("chat_messages") or []
    if not any(m.get("content") == message for m in msgs):
        msgs.append({"role": "user", "content": message})
        st.session_state["chat_messages"] = msgs

    st.session_state["current_screen"] = "planning"
    st.session_state["plan_query"] = None
    st.session_state["planning_resume_feedback"] = message
    st.rerun()
