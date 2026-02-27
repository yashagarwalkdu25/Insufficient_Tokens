"""Onboarding: single-input trip intake."""
from __future__ import annotations

import re
from datetime import date, timedelta

import streamlit as st


EXAMPLES = [
    ("Solo Rishikesh ₹15K", "Plan a 4-day solo backpacking trip to Rishikesh under ₹15,000. Adventure and spiritual vibes. From Delhi."),
    ("Family Goa ₹60K",     "5-day family vacation in Goa with 2 kids, budget ₹60,000. Beaches and water sports. From Mumbai."),
    ("Weekend Jaipur",      "Weekend trip to Jaipur from Delhi. Midrange, culture and photography. 2 days."),
    ("Luxury Kerala",       "Luxury 5-day Kerala trip. Backwaters and Munnar. Budget ₹1,00,000. Couple."),
]

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

VEHICLE_OPTIONS = [
    ("any",         "No preference"),
    ("flight",      "✈️  Flight"),
    ("train",       "🚂  Train"),
    ("bus",         "🚌  Bus"),
    ("self_drive",  "🚗  Self-drive / Own car"),
    ("cab",         "🚕  Cab / Taxi"),
    ("bike",        "🏍️  Bike / Motorcycle"),
    ("mixed",       "🔀  Mixed / Whatever's cheapest"),
]


def render_onboarding() -> str | None:
    """Render onboarding UI. Returns query string or None."""
    if "onb_freetext_pick" in st.session_state:
        st.session_state["onb_freetext"] = st.session_state.pop("onb_freetext_pick")

    st.markdown('<div class="ts-separator"></div>', unsafe_allow_html=True)

    # ── Primary: free-text input ──────────────────────────────────────
    free_text = st.text_area(
        "Describe your trip",
        height=110,
        placeholder="e.g.  4-day solo trip to Rishikesh, ₹15K budget, adventure & yoga vibes",
        key="onb_freetext",
        label_visibility="collapsed",
    )

    # ── Example chips ─────────────────────────────────────────────────
    chip_cols = st.columns(len(EXAMPLES))
    for col, (label, prompt) in zip(chip_cols, EXAMPLES):
        with col:
            st.markdown('<div class="ts-dest-btn">', unsafe_allow_html=True)
            if st.button(label, key=f"ex_{label}", use_container_width=True):
                st.session_state["onb_freetext_pick"] = prompt
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    # ── Optional details expander ─────────────────────────────────────
    with st.expander("Add trip details  ·  optional", expanded=False):

        # Row 1: origin + dates
        c1, c2, c3 = st.columns([1.2, 1, 1])
        with c1:
            st.text_input("Departing from", value="Delhi", key="onb_origin")
        with c2:
            st.date_input("Start date", value=date.today() + timedelta(days=7), key="onb_start")
        with c3:
            st.date_input("End date", value=date.today() + timedelta(days=10), key="onb_end")

        # Row 2: budget — slider + text box with ₹ prefix
        if "onb_budget" not in st.session_state:
            st.session_state["onb_budget"] = 15000
        if "onb_budget_text" not in st.session_state:
            st.session_state["onb_budget_text"] = "₹15,000"

        def _slider_changed():
            v = st.session_state["onb_budget"]
            st.session_state["onb_budget_text"] = f"₹{v:,}"

        def _text_changed():
            raw = st.session_state["onb_budget_text"].replace("₹", "").replace(",", "").strip()
            try:
                val = int(max(1, min(500000, int(float(raw)))))
            except (ValueError, TypeError):
                val = st.session_state["onb_budget"]
            st.session_state["onb_budget"] = val
            st.session_state["onb_budget_text"] = f"₹{val:,}"

        st.markdown(
            '<p style="margin:0 0 0.3rem 0; font-size:0.88rem; font-weight:500; '
            'color:var(--ts-text-muted);">Budget</p>',
            unsafe_allow_html=True,
        )
        bs_col, bn_col = st.columns([4, 1])
        with bs_col:
            st.slider(
                "Budget",
                min_value=1,
                max_value=500000,
                step=500,
                format="₹%d",
                key="onb_budget",
                label_visibility="collapsed",
                on_change=_slider_changed,
            )
        with bn_col:
            st.text_input(
                "Budget text",
                key="onb_budget_text",
                label_visibility="collapsed",
                on_change=_text_changed,
            )

        # Row 3: traveler type + travel style + vehicle
        c4, c5, c6 = st.columns(3)
        with c4:
            st.selectbox(
                "Traveler type",
                options=["Solo", "Couple", "Family", "Group"],
                key="onb_traveler",
            )
        with c5:
            st.selectbox(
                "Travel style",
                options=["Backpacker", "Midrange", "Luxury"],
                key="onb_style",
            )
        with c6:
            st.selectbox(
                "Mode of travel",
                options=[k for k, _ in VEHICLE_OPTIONS],
                format_func=lambda k: dict(VEHICLE_OPTIONS).get(k, k),
                key="onb_vehicle",
            )

        # Row 4: interests full width
        st.multiselect(
            "Interests",
            options=[k for k, _ in INTEREST_OPTIONS],
            format_func=lambda k: dict(INTEREST_OPTIONS).get(k, k),
            default=["adventure", "culture"],
            key="onb_interests",
        )

    # ── AI Travel Negotiator toggle ───────────────────────────────────
    st.markdown("""
<div style="
  background: linear-gradient(135deg, #f0eaf8 0%, #e8eef8 100%);
  border: 1.5px solid #c4aee8;
  border-radius: 12px;
  padding: 1rem 1.25rem;
  margin: 1rem 0 0.5rem;
  display: flex;
  align-items: flex-start;
  gap: 0.85rem;
">
  <div style="font-size:1.6rem;line-height:1;">🤝</div>
  <div style="flex:1;">
    <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.2rem;">
      <span style="font-weight:700;font-size:0.95rem;color:#3d1f6e;">AI Travel Negotiator</span>
      <span style="background:#6b3fa0;color:#fff;font-size:0.62rem;font-weight:700;
                   letter-spacing:0.07em;text-transform:uppercase;padding:0.1rem 0.45rem;
                   border-radius:20px;">Beta</span>
    </div>
    <div style="font-size:0.82rem;color:#5a4a6e;line-height:1.5;">
      Generates three negotiated bundles — Budget Saver, Best Value, Experience Max —
      with cost breakdowns and trade-off analysis before building your itinerary.
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

    use_negotiator = st.checkbox(
        "Enable AI Travel Negotiator  ·  compare bundles before building itinerary",
        value=st.session_state.get("onb_use_negotiator", True),
        key="onb_use_negotiator",
    )
    st.session_state["use_negotiator"] = use_negotiator

    # ── Submit ────────────────────────────────────────────────────────
    st.markdown('<div style="height:0.5rem"></div>', unsafe_allow_html=True)
    if st.button("Plan My Journey", type="primary", use_container_width=True, key="onb_submit"):
        if free_text and free_text.strip():
            extra = _build_extra_context(free_text.strip())
            return (free_text.strip() + ("  " + extra if extra else "")).strip()
        st.error("Describe your trip above, or try one of the examples.")
        return None
    return None


def _parse_budget_from_text(text: str) -> int | None:
    """Extract budget (INR) from free text. Returns None if none found. Prefer last mention (user's edit)."""
    if not (text or text.strip()):
        return None
    # Match ₹X, ₹X,XXX, ₹Xk, Xk, X lakh, budget X, under ₹X, under X
    candidates: list[int] = []
    # ₹25,000 or ₹25k or ₹1,00,000
    for m in re.finditer(r"₹\s*([\d,]+)\s*(?:k|lakh|lac)?", text, re.IGNORECASE):
        raw = m.group(1).replace(",", "")
        try:
            n = int(raw)
            if "lakh" in text[m.start() : m.end()].lower() or "lac" in text[m.start() : m.end()].lower():
                n *= 100000
            elif "k" in text[m.start() : m.end()].lower():
                n = n * 1000 if n < 1000 else n
            if 100 <= n <= 1000000:
                candidates.append(n)
        except ValueError:
            pass
    # 15k, 20k, 60K (standalone)
    for m in re.finditer(r"\b(\d+)\s*k\b", text, re.IGNORECASE):
        try:
            n = int(m.group(1))
            n = n * 1000 if n < 1000 else n
            if 1000 <= n <= 1000000:
                candidates.append(n)
        except ValueError:
            pass
    # "budget 25000" or "under 20000"
    for m in re.finditer(r"(?:budget|under)\s*[₹]?\s*([\d,]+)", text, re.IGNORECASE):
        try:
            n = int(m.group(1).replace(",", ""))
            if 100 <= n <= 1000000:
                candidates.append(n)
        except ValueError:
            pass
    return candidates[-1] if candidates else None


def _build_extra_context(free_text: str = "") -> str:
    parts: list[str] = []

    origin = (st.session_state.get("onb_origin") or "").strip()
    if origin and origin.lower() != "delhi":
        parts.append(f"from {origin}")

    # Use budget from free text if user edited it (e.g. quick-click then "₹25,000"); else use expander slider
    budget: int = _parse_budget_from_text(free_text) if free_text else None
    if budget is None:
        budget = st.session_state.get("onb_budget", 15000)
    # Do not write to onb_budget/onb_budget_text here — widget already instantiated this run
    parts.append(f"budget ₹{budget:,}")

    start = st.session_state.get("onb_start")
    end   = st.session_state.get("onb_end")
    if start and end:
        days = max(1, (end - start).days + 1)
        parts.append(f"{days} days from {start} to {end}")

    traveler = st.session_state.get("onb_traveler", "Solo")
    if traveler and traveler != "Solo":
        parts.append(f"traveling as {traveler.lower()}")

    style = st.session_state.get("onb_style", "Midrange")
    if style:
        parts.append(f"{style.lower()} style")

    vehicle = st.session_state.get("onb_vehicle", "any")
    if vehicle and vehicle != "any":
        vehicle_label = dict(VEHICLE_OPTIONS).get(vehicle, vehicle)
        # Strip emoji prefix for the query
        vehicle_clean = vehicle_label.split("  ")[-1] if "  " in vehicle_label else vehicle_label
        parts.append(f"preferred transport: {vehicle_clean}")

    interests: list[str] = st.session_state.get("onb_interests", [])
    if interests:
        interest_labels = [dict(INTEREST_OPTIONS).get(k, k) for k in interests]
        parts.append("interests: " + ", ".join(interest_labels))

    return ". ".join(parts)
