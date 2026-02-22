"""Onboarding: editorial-style trip intake with form and free-text."""
from __future__ import annotations

import streamlit as st
from datetime import date, timedelta
from app.data.india_cities import INDIA_CITIES


INTEREST_OPTIONS = [
    ("adventure", "Adventure"),
    ("culture", "Culture & Heritage"),
    ("spiritual", "Spiritual"),
    ("beaches", "Beaches"),
    ("nature", "Nature & Hills"),
    ("food", "Food & Culinary"),
    ("shopping", "Shopping"),
    ("photography", "Photography"),
    ("wildlife", "Wildlife"),
    ("trekking", "Trekking"),
    ("nightlife", "Nightlife"),
    ("wellness", "Wellness & Yoga"),
]


def render_onboarding() -> str | None:
    """Render onboarding UI. Returns query string or None."""
    popular_cities = sorted(INDIA_CITIES.keys())

    # Apply quick-pick / example choices before widgets are created (Streamlit forbids
    # writing to a widget key after that widget exists).
    if "onb_dest_pick" in st.session_state:
        st.session_state["onb_dest"] = st.session_state.pop("onb_dest_pick")
    if "onb_freetext_pick" in st.session_state:
        st.session_state["onb_freetext"] = st.session_state.pop("onb_freetext_pick")

    st.markdown('<div class="ts-separator"></div>', unsafe_allow_html=True)

    col_form, col_free = st.columns([1.1, 0.9], gap="large")

    # ── Left: structured form ────────────────────────────────────────
    with col_form:
        st.markdown("### Where to next?")
        st.caption("Fill in the details and we'll craft the perfect itinerary.")

        origin = st.text_input(
            "Departing from",
            value="Delhi",
            placeholder="e.g. Delhi, Mumbai, Bangalore...",
            key="onb_origin",
        )

        destination = st.text_input(
            "Destination",
            value="",
            placeholder="Type any city — Goa, Manali, Kasol, Ooty...",
            key="onb_dest",
        )

        st.caption("Quick picks")
        pick_cols = st.columns(5)
        for i, city in enumerate(popular_cities[:10]):
            with pick_cols[i % 5]:
                cont = st.container()
                cont.markdown('<div class="ts-dest-btn">', unsafe_allow_html=True)
                if cont.button(city, key=f"pick_{city}", use_container_width=True):
                    st.session_state["onb_dest_pick"] = city
                    st.rerun()
                cont.markdown('</div>', unsafe_allow_html=True)

        r1c1, r1c2 = st.columns(2)
        with r1c1:
            traveler_type = st.selectbox(
                "Traveler type",
                options=["Solo", "Couple", "Family", "Group"],
                key="onb_traveler",
            )
        with r1c2:
            travel_style = st.selectbox(
                "Travel style",
                options=["Backpacker", "Midrange", "Luxury"],
                key="onb_style",
            )

        budget = st.slider(
            "Budget (INR)",
            min_value=5000,
            max_value=500000,
            step=1000,
            value=15000,
            format="₹%d",
            key="onb_budget",
        )

        d1, d2 = st.columns(2)
        with d1:
            start_date = st.date_input("Start date", value=date.today() + timedelta(days=7), key="onb_start")
        with d2:
            end_date = st.date_input("End date", value=start_date + timedelta(days=2), key="onb_end")

        interests = st.multiselect(
            "Interests",
            options=[k for k, _ in INTEREST_OPTIONS],
            format_func=lambda k: dict(INTEREST_OPTIONS).get(k, k),
            default=["adventure", "culture"],
            key="onb_interests",
        )

    # ── Right: free-text & examples ──────────────────────────────────
    with col_free:
        st.markdown("### Or just tell us")
        st.caption("Describe your dream trip in your own words — Hindi, English, Hinglish, anything goes.")

        free_text = st.text_area(
            "Describe your trip",
            value="",
            height=140,
            placeholder="e.g. 4-day solo trip to Rishikesh, ₹15K budget, adventure & yoga vibes",
            key="onb_freetext",
            label_visibility="collapsed",
        )

        st.markdown("**Try these:**")
        ex_cols = st.columns(2)
        with ex_cols[0]:
            if st.button("Solo Rishikesh ₹15K", key="ex1", use_container_width=True):
                st.session_state["onb_freetext_pick"] = "Plan a 4-day solo backpacking trip to Rishikesh under ₹15,000. Adventure and spiritual. From Delhi."
                st.rerun()
            if st.button("Family Goa ₹60K", key="ex2", use_container_width=True):
                st.session_state["onb_freetext_pick"] = "5-day family vacation in Goa with 2 kids. Budget ₹60,000. Beaches and water sports. From Mumbai."
                st.rerun()
        with ex_cols[1]:
            if st.button("Weekend Jaipur", key="ex3", use_container_width=True):
                st.session_state["onb_freetext_pick"] = "Weekend trip to Jaipur from Delhi. Midrange, culture and photography. 2 days."
                st.rerun()
            if st.button("Luxury Kerala", key="ex4", use_container_width=True):
                st.session_state["onb_freetext_pick"] = "Luxury 5-day Kerala trip. Backwaters and Munnar. Budget ₹1,00,000."
                st.rerun()

        st.markdown("""
        <div style="margin-top:1.5rem; padding:1rem 1.2rem; background:rgba(26,86,83,0.04);
             border-radius:12px; border-left:4px solid #C5A55A;">
          <p style="margin:0; font-size:0.88rem; color:#1E2832;">
            <strong style="color:#1A5653;">TripSaathi works best when you share:</strong><br/>
            destination, budget, dates, interests, and who you're traveling with.
          </p>
        </div>
        """, unsafe_allow_html=True)

    # ── Submit ───────────────────────────────────────────────────────
    st.markdown('<div class="ts-separator"></div>', unsafe_allow_html=True)
    if st.button("Plan My Journey", type="primary", use_container_width=True, key="onb_submit"):
        if free_text and free_text.strip():
            return free_text.strip()
        dest = (destination or "").strip()
        if not dest:
            st.error("Please enter a destination or describe your trip.")
            return None
        origin_city = (origin or "Delhi").strip()
        style_lower = travel_style.lower()
        days = max(1, (end_date - start_date).days + 1)
        parts = [
            f"{days}-day",
            traveler_type.lower(),
            f"trip to {dest}",
            f"from {origin_city}",
            f"budget ₹{budget:,}",
            f"from {start_date} to {end_date}",
            f"style {style_lower}",
        ]
        if interests:
            parts.append("interests: " + ", ".join(interests))
        return " ".join(parts)
    return None
