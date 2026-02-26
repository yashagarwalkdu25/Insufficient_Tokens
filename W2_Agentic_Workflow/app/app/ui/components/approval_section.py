"""Approval section: review summary with approve / modify / start over."""
from __future__ import annotations

import streamlit as st
from typing import Any


def render_approval(state: dict[str, Any], on_approve: callable, on_modify: callable, on_reset: callable) -> None:
    approval_type = state.get("approval_type") or "research"

    if approval_type == "destination":
        options = state.get("destination_options") or []

        if "selected_destination_idx" not in st.session_state:
            st.session_state["selected_destination_idx"] = 0

        # Build the options HTML inside the card
        options_html = ""
        for idx, o in enumerate(options):
            city = o.get("city", "")
            state_name = o.get("state", "")
            why = o.get("why", "")
            budget = o.get("budget", "")
            options_html += (
                f'<div class="ts-tip-card" style="margin:8px 0;">'
                f'<strong>{city}, {state_name}</strong>'
                f'<br/><span style="font-size:0.88rem;color:var(--ts-text-muted);">{why}</span>'
                f'<br/><span style="font-size:0.82rem;color:var(--ts-saffron);">{budget}</span>'
                f'</div>'
            )

        st.markdown(
            f'<div class="ts-approval-card">'
            f'<h3 style="margin:0 0 1rem 0;">Choose your destination</h3>'
            f'{options_html}'
            f'</div>',
            unsafe_allow_html=True,
        )

        if options:
            selected_label = st.radio(
                "Select destination",
                options=[f"{o.get('city', '')}, {o.get('state', '')}" for o in options],
                index=st.session_state["selected_destination_idx"],
                key="dest_radio",
                label_visibility="collapsed",
            )
            st.session_state["selected_destination_idx"] = next(
                (i for i, o in enumerate(options)
                 if f"{o.get('city', '')}, {o.get('state', '')}" == selected_label),
                0,
            )

    elif approval_type == "itinerary":
        trip = state.get("trip") or {}
        dest = trip.get("destination", "")
        start = trip.get("start_date", "")
        end = trip.get("end_date", "")
        cost = trip.get("total_cost", 0)
        st.markdown(
            f'<div class="ts-approval-card">'
            f'<h3 style="margin:0 0 0.75rem 0;">Review your itinerary</h3>'
            f'<div style="font-size:1.1rem;">'
            f'<strong>{dest}</strong> &nbsp;·&nbsp; {start} → {end} &nbsp;·&nbsp; ₹{cost:,.0f}'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    else:
        st.markdown(
            '<div class="ts-approval-card">'
            '<h3 style="margin:0 0 0.5rem 0;">Review research</h3>'
            '<p style="margin:0;color:var(--ts-text-muted);">'
            'Flights, hotels, and activities have been gathered. Proceed to build your itinerary.'
            '</p>'
            '</div>',
            unsafe_allow_html=True,
        )

    c1, c2, c3 = st.columns(3)
    with c1:
        approve_label = "Select & Continue" if approval_type == "destination" else "Approve"
        if st.button(approve_label, type="primary", key="approve_btn", use_container_width=True):
            if approval_type == "destination":
                selected_idx = st.session_state.get("selected_destination_idx", 0)
                options = state.get("destination_options", [])
                if selected_idx < len(options):
                    selected_dest = options[selected_idx].get("city", "")
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
