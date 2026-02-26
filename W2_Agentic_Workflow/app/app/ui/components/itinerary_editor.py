"""Itinerary editor: editorial day cards with rich item layout."""
from __future__ import annotations

import streamlit as st
from typing import Any

ICON_MAP = {
    "transport":  ("🚌",  "ts-icon-transport"),
    "hotel":      ("🏡",  "ts-icon-hotel"),
    "activity":   ("🎭",  "ts-icon-activity"),
    "meal":       ("🍽️", "ts-icon-meal"),
    "free_time":  ("🏖️", "ts-icon-free"),
}

TRANSPORT_MODE_ICON = {
    "flight":  "✈️",
    "train":   "🚂",
    "bus":     "🚌",
    "cab":     "🚕",
    "auto":    "🛺",
    "walk":    "🚶",
    "metro":   "🚇",
    "ferry":   "⛴️",
    "bike":    "🏍️",
}

DAY_COLORS = ["ts-day-1", "ts-day-2", "ts-day-3", "ts-day-4", "ts-day-5", "ts-day-6", "ts-day-7"]


def render_itinerary(trip: dict[str, Any], state: dict[str, Any]) -> None:
    days = trip.get("days") or []
    if not days:
        st.info("No itinerary yet.")
        return

    for day in days:
        day_num = day.get("day_number", 0)
        day_title = day.get("title", f"Day {day_num}")
        day_date = day.get("date", "")
        day_cost = day.get("day_cost", 0)
        items = day.get("items") or []
        color_cls = DAY_COLORS[(day_num - 1) % len(DAY_COLORS)]
        tip = day.get("tip_of_the_day")

        with st.expander(
            f"Day {day_num}  ·  {day_date}  ·  {day_title}  ·  ₹{day_cost:,.0f}",
            expanded=(day_num == 1),
        ):
            if tip:
                st.markdown(
                    f'<div style="background:rgba(197,165,90,0.1); border-left:3px solid var(--ts-gold);'
                    f' padding:8px 12px; border-radius:8px; margin-bottom:10px; font-size:0.88rem;">'
                    f'💡 <em>{tip}</em></div>',
                    unsafe_allow_html=True,
                )

            for idx, item in enumerate(items):
                itype = item.get("item_type", "activity")
                emoji, icon_cls = ICON_MAP.get(itype, ("•", "ts-icon-activity"))
                if itype == "transport":
                    mode = (item.get("travel_mode") or "").lower()
                    if not mode:
                        title_lower = item.get("title", "").lower()
                        if "flight" in title_lower or "fly" in title_lower or "airport" in title_lower:
                            mode = "flight"
                        elif "train" in title_lower or "express" in title_lower or "railway" in title_lower or "shatabdi" in title_lower:
                            mode = "train"
                        elif "bus" in title_lower:
                            mode = "bus"
                        elif "cab" in title_lower or "taxi" in title_lower or "uber" in title_lower or "ola" in title_lower:
                            mode = "cab"
                        elif "auto" in title_lower or "rickshaw" in title_lower:
                            mode = "auto"
                        elif "walk" in title_lower:
                            mode = "walk"
                        elif "metro" in title_lower:
                            mode = "metro"
                    emoji = TRANSPORT_MODE_ICON.get(mode, "🚌")
                time_str = item.get("time", "")
                title = item.get("title", "")
                cost = item.get("cost", 0)
                desc = item.get("description", "")

                cost_html = (
                    f'<span class="ts-itin-cost">₹{cost:,.0f}</span>' if cost else ''
                )
                st.markdown(
                    f'<div class="ts-itin-item">'
                    f'  <div class="ts-itin-icon {icon_cls}">{emoji}</div>'
                    f'  <div style="flex:1;">'
                    f'    <span class="ts-itin-time">{time_str}</span> '
                    f'    <span class="ts-itin-title">{title}</span>'
                    + (f'<br/><span style="font-size:0.82rem; color:var(--ts-text-muted);">{desc[:150]}</span>' if desc else '')
                    + f'  </div>'
                    + cost_html
                    + f'</div>',
                    unsafe_allow_html=True,
                )

                contact = item.get("contact_info")
                if contact:
                    st.caption(f"📍 {contact}")

                opening = item.get("opening_hours")
                if isinstance(opening, dict) and opening:
                    hrs = " · ".join(f"{k}: {v}" for k, v in list(opening.items())[:3])
                    st.caption(f"🕐 {hrs}")
                elif isinstance(opening, str):
                    st.caption(f"🕐 {opening}")

                dur = item.get("travel_duration_to_next")
                mode = item.get("travel_mode_to_next") or "drive"
                if dur is not None and dur > 0 and idx < len(items) - 1:
                    mode_icon = {"driving": "🚗", "walking": "🚶", "transit": "🚌"}.get(mode, "🚗")
                    st.markdown(
                        f'<div class="ts-travel-badge">{mode_icon} {dur} min to next stop</div>',
                        unsafe_allow_html=True,
                    )

                booking_url = item.get("booking_url")
                if booking_url:
                    st.link_button("Book now", url=booking_url, key=f"book_{day_num}_{idx}")
