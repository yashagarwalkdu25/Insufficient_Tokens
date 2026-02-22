"""Chat sidebar: trip modification chat with quick action chips."""
from __future__ import annotations

import streamlit as st


def render_chat_sidebar() -> None:
    with st.sidebar:
        # Header row with close button
        st.markdown(
            '<div style="display:flex; align-items:center; gap:0.6rem; margin-bottom:0.8rem;">'
            '<h3 style="margin:0; flex:1; font-size:1.15rem;">Modify Trip</h3>'
            '</div>'
            '<p style="font-size:0.8rem; color:var(--ts-text-muted); margin:0 0 0.6rem 0;">Ask TripSaathi to refine your journey or answer questions.</p>',
            unsafe_allow_html=True,
        )

        # Close sidebar button
        if st.button("Close panel", key="close_modify_sidebar", use_container_width=True):
            st.session_state["show_modify_sidebar"] = False
            st.rerun()

        st.markdown('<div style="height:4px;"></div>', unsafe_allow_html=True)

        # Chat messages
        messages = st.session_state.get("chat_messages") or []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "user":
                st.chat_message("user").write(content)
            else:
                st.chat_message("assistant").write(content)
        
        # Show any conversation response from state
        trip_state = st.session_state.get("trip_state") or {}
        conv_response = trip_state.get("conversation_response")
        if conv_response and not any(m.get("content") == conv_response for m in messages):
            st.chat_message("assistant").write(conv_response)
            # Add to messages so it persists
            messages.append({"role": "assistant", "content": conv_response})
            st.session_state["chat_messages"] = messages

        # Quick actions
        st.caption("Quick actions")
        q1, q2 = st.columns(2)
        with q1:
            if st.button("Make it cheaper", key="q_cheap", use_container_width=True):
                st.session_state["pending_feedback"] = "Make it cheaper, reduce budget"
            if st.button("More adventure", key="q_adv", use_container_width=True):
                st.session_state["pending_feedback"] = "Add more adventure activities"
        with q2:
            if st.button("Change stays", key="q_hotel", use_container_width=True):
                st.session_state["pending_feedback"] = "Change to a different hotel"
            if st.button("Different dates", key="q_dates", use_container_width=True):
                st.session_state["pending_feedback"] = "I want to change my travel dates"

        st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)

        # Chat input
        feedback = st.chat_input("Type your request or question...")
        if feedback:
            st.session_state["pending_feedback"] = feedback
        pending = st.session_state.get("pending_feedback")
        if pending:
            st.session_state["pending_feedback"] = None
            st.session_state["current_screen"] = "planning"
            st.session_state["plan_query"] = None
            st.session_state["planning_resume_feedback"] = pending
            msgs = st.session_state.get("chat_messages") or []
            msgs.append({"role": "user", "content": pending})
            st.session_state["chat_messages"] = msgs
            st.rerun()
