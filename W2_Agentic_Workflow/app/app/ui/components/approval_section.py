"""Approval section: review summary with approve / modify / start over."""
from __future__ import annotations

import streamlit as st
from typing import Any


def render_approval(state: dict[str, Any], on_approve: callable, on_modify: callable, on_reset: callable) -> None:
    approval_type = state.get("approval_type") or "research"

    st.markdown('<div class="ts-approval-card">', unsafe_allow_html=True)

    if approval_type == "destination":
        st.markdown("### Choose your destination")
        options = state.get("destination_options") or []
        
        # Initialize selected destination in session state
        if "selected_destination_idx" not in st.session_state:
            st.session_state["selected_destination_idx"] = 0
        
        for idx, o in enumerate(options):
            col1, col2 = st.columns([0.1, 0.9])
            with col1:
                if st.radio(
                    "Select",
                    [idx],
                    index=0 if st.session_state["selected_destination_idx"] == idx else None,
                    key=f"dest_radio_{idx}",
                    label_visibility="collapsed"
                ):
                    st.session_state["selected_destination_idx"] = idx
            
            with col2:
                st.markdown(
                    f'<div class="ts-tip-card" style="margin:8px 0;">'
                    f'<strong>{o.get("city", "")}, {o.get("state", "")}</strong>'
                    f'<br/><span style="font-size:0.88rem; color:var(--ts-text-muted);">{o.get("why", "")}</span>'
                    f'<br/><span style="font-size:0.82rem; color:var(--ts-accent);">{o.get("budget", "")}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    elif approval_type == "itinerary":
        trip = state.get("trip") or {}
        dest = trip.get("destination", "")
        start = trip.get("start_date", "")
        end = trip.get("end_date", "")
        cost = trip.get("total_cost", 0)
        st.markdown("### Review your itinerary")
        st.markdown(
            f'<div style="font-size:1.1rem; margin:8px 0;">'
            f'<strong>{dest}</strong> &nbsp;·&nbsp; {start} → {end} &nbsp;·&nbsp; ₹{cost:,.0f}</div>',
            unsafe_allow_html=True,
        )

    else:
        st.markdown("### Review research")
        st.write("Flights, hotels, and activities have been gathered. Proceed to build your itinerary.")

    st.markdown('</div>', unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        approve_label = "Select & Continue" if approval_type == "destination" else "Approve"
        if st.button(approve_label, type="primary", key="approve_btn", use_container_width=True):
            # For destination approval, update trip_request with selected destination
            if approval_type == "destination":
                selected_idx = st.session_state.get("selected_destination_idx", 0)
                options = state.get("destination_options", [])
                if selected_idx < len(options):
                    selected_dest = options[selected_idx].get("city", "")
                    # Update trip_request with selected destination
                    if state.get("trip_request"):
                        state["trip_request"]["destination"] = selected_dest
                        st.session_state["trip_state"] = state
            on_approve()
    with c2:
        if st.button("Modify", key="modify_btn", use_container_width=True):
            on_modify()
    with c3:
        if st.button("Start over", key="reset_btn", use_container_width=True):
            on_reset()
