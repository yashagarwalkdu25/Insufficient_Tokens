"""Trip dashboard: editorial top bar, tabs, action bar."""
from __future__ import annotations

import streamlit as st
from typing import Any


def render_trip_dashboard(state: dict[str, Any]) -> None:
    trip = state.get("trip") or {}
    vibe_score = state.get("vibe_score") or {}
    destination = trip.get("destination", "Trip")
    start = trip.get("start_date", "")
    end = trip.get("end_date", "")
    total_cost = trip.get("total_cost", 0)
    score = vibe_score.get("overall_score")
    tagline = vibe_score.get("tagline", "")
    n_days = len(trip.get("days") or [])

    # Top summary bar
    st.markdown(f"""
    <div class="ts-card" style="display:flex; flex-wrap:wrap; align-items:center; gap:1.5rem; padding:1.3rem 1.6rem;">
      <div style="flex:1; min-width:200px;">
        <h2 style="margin:0 0 0.15rem 0; font-size:1.8rem !important;">{destination}</h2>
        <span style="color:var(--ts-text-muted); font-size:0.88rem;">{start} → {end} · {n_days} days</span>
      </div>
      <div style="text-align:center;">
        <div class="ts-metric-value" style="font-size:1.5rem;">₹{total_cost:,.0f}</div>
        <div class="ts-metric-label">Total cost</div>
      </div>
      {"" if score is None else f'''
      <div style="text-align:center;">
        <div class="ts-metric-value" style="font-size:1.5rem; color:var(--ts-saffron);">{score}/100</div>
        <div class="ts-metric-label">Vibe score</div>
      </div>
      '''}
    </div>
    """, unsafe_allow_html=True)

    if tagline:
        st.caption(f"_{tagline}_")

    # Share button
    share_col, _, _ = st.columns([1, 3, 1])
    with share_col:
        if st.button("Share trip", key="dashboard_share_btn", use_container_width=True):
            st.session_state["show_share_modal"] = True

    st.markdown('<div class="ts-separator"></div>', unsafe_allow_html=True)

    # Tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Itinerary",
        "Map",
        "Budget",
        "Local Secrets",
        "Vibe Score",
        "AI Reasoning",
    ])
    with tab1:
        from app.ui.components.itinerary_editor import render_itinerary
        render_itinerary(trip, state)
    with tab2:
        from app.ui.components.map_view import render_map
        render_map(trip)
    with tab3:
        from app.ui.components.budget_view import render_budget
        render_budget(state.get("budget_tracker"), state)
    with tab4:
        from app.ui.components.local_tips_view import render_local_tips
        render_local_tips(
            state.get("local_tips") or [],
            state.get("hidden_gems") or [],
            state.get("events") or [],
        )
    with tab5:
        from app.ui.components.vibe_score_view import render_vibe_score
        render_vibe_score(state.get("vibe_score"))
    with tab6:
        from app.ui.components.reasoning_view import render_reasoning
        render_reasoning(state.get("agent_decisions") or [])

    # Action bar
    st.markdown('<div class="ts-separator"></div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Approve & Export", type="primary", use_container_width=True, key="act_approve"):
            st.session_state["show_approval"] = True
            st.rerun()
    with c2:
        is_modify_active = st.session_state.get("show_modify_sidebar", False)
        modify_label = "Close Chat" if is_modify_active else "Modify Trip"
        if st.button(modify_label, use_container_width=True, key="act_modify"):
            if is_modify_active:
                st.session_state["show_modify_sidebar"] = False
                st.session_state["modify_chat_active"] = False
            else:
                st.session_state["show_modify_sidebar"] = True
                st.session_state["modify_chat_active"] = True
            st.rerun()
    with c3:
        if st.button("New Journey", use_container_width=True, key="act_new"):
            st.session_state["trip_state"] = {}
            st.session_state["current_screen"] = "onboarding"
            st.session_state["chat_messages"] = []
            st.session_state["show_modify_sidebar"] = False
            st.session_state["modify_chat_active"] = False
            st.rerun()
