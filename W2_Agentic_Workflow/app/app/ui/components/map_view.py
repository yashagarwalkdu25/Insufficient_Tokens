"""Map view: Folium map with day-wise markers and route polylines."""
from __future__ import annotations

import streamlit as st
from typing import Any

try:
    import folium
    from streamlit_folium import st_folium
    HAS_FOLIUM = True
except ImportError:
    HAS_FOLIUM = False

DAY_COLORS = ["#1A5653", "#E8772E", "#C5A55A", "#2A7A76", "#F09A5B", "#7A8B8A", "#2D8B5F"]


def render_map(trip: dict[str, Any]) -> None:
    if not HAS_FOLIUM:
        st.info("Install `folium` and `streamlit-folium` for the interactive map.")
        return
    days = trip.get("days") or []
    if not days:
        st.info("No itinerary to show on the map yet.")
        return

    lat, lon = 20.5937, 78.9629
    for day in days:
        for item in day.get("items") or []:
            la, ln = item.get("latitude"), item.get("longitude")
            if la is not None and ln is not None:
                lat, lon = float(la), float(ln)
                break
        if lat != 20.5937:
            break

    tiles = "CartoDB positron"
    m = folium.Map(location=[lat, lon], zoom_start=11, tiles=tiles)

    day_filter = ["All Days"] + [f"Day {d.get('day_number')}" for d in days]
    choice = st.selectbox("Filter by day", day_filter, key="map_day_filter")
    day_idx = day_filter.index(choice) - 1 if choice != "All Days" else -1

    for di, day in enumerate(days):
        if day_idx >= 0 and di != day_idx:
            continue
        color = DAY_COLORS[di % len(DAY_COLORS)]
        points = []
        for item in day.get("items") or []:
            la, ln = item.get("latitude"), item.get("longitude")
            if la is not None and ln is not None:
                points.append((float(la), float(ln)))
                popup_html = (
                    f"<div style='font-family:Plus Jakarta Sans,system-ui;'>"
                    f"<strong>{item.get('title','')}</strong><br/>"
                    f"{item.get('time','')} · ₹{item.get('cost',0):,.0f}</div>"
                )
                folium.CircleMarker(
                    [la, ln],
                    radius=8,
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.85,
                    popup=folium.Popup(popup_html, max_width=250),
                    tooltip=item.get("title"),
                ).add_to(m)
        if len(points) >= 2:
            folium.PolyLine(points, color=color, weight=3, opacity=0.6, dash_array="6,4").add_to(m)

    st_folium(m, width=700, height=480, returned_objects=[])
