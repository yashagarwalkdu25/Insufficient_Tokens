"""Map view: Folium map with destination marker, day-wise activity markers, and route polylines."""
from __future__ import annotations

import logging
import streamlit as st
from typing import Any

try:
    import folium
    from streamlit_folium import st_folium
    HAS_FOLIUM = True
except ImportError:
    HAS_FOLIUM = False

from app.data.india_cities import get_city

logger = logging.getLogger(__name__)

DAY_COLORS = ["#1A5653", "#E8772E", "#C5A55A", "#2A7A76", "#F09A5B", "#7A8B8A", "#2D8B5F"]

ITEM_TYPE_ICONS = {
    "activity": "star",
    "meal": "cutlery",
    "hotel": "home",
    "transport": "plane",
    "free_time": "cloud",
}


def _get_destination_coords(trip: dict[str, Any]) -> tuple[float, float] | None:
    """Get coordinates for the trip destination from india_cities or itinerary items."""
    dest = (trip.get("destination") or "").strip()
    if dest:
        city = get_city(dest)
        if city and city.get("latitude") and city.get("longitude"):
            return float(city["latitude"]), float(city["longitude"])

    # Scan itinerary items for any coordinates
    for day in trip.get("days") or []:
        for item in day.get("items") or []:
            lat = item.get("latitude")
            lon = item.get("longitude")
            if lat is not None and lon is not None:
                return float(lat), float(lon)

    return None


def _collect_markers(days: list[dict], day_idx: int) -> list[dict]:
    """Collect all map markers from itinerary items that have coordinates."""
    markers = []
    for di, day in enumerate(days):
        if day_idx >= 0 and di != day_idx:
            continue
        color = DAY_COLORS[di % len(DAY_COLORS)]
        day_num = day.get("day_number", di + 1)
        for item in day.get("items") or []:
            lat = item.get("latitude")
            lon = item.get("longitude")
            if lat is not None and lon is not None:
                markers.append({
                    "lat": float(lat),
                    "lon": float(lon),
                    "title": item.get("title", ""),
                    "time": item.get("time", ""),
                    "cost": item.get("cost", 0),
                    "item_type": item.get("item_type", "activity"),
                    "day_num": day_num,
                    "color": color,
                    "description": item.get("description", ""),
                })
    return markers


def render_map(trip: dict[str, Any]) -> None:
    if not HAS_FOLIUM:
        st.info("Install `folium` and `streamlit-folium` for the interactive map.")
        return

    days = trip.get("days") or []
    dest = trip.get("destination") or "Destination"

    if not days:
        st.info("No itinerary to show on the map yet.")
        return

    # Get destination center coordinates
    dest_coords = _get_destination_coords(trip)
    if dest_coords:
        center_lat, center_lon = dest_coords
    else:
        center_lat, center_lon = 20.5937, 78.9629  # India center

    # Use OpenStreetMap tiles (reliable, always works, no API key needed)
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=13 if dest_coords else 5,
        tiles="OpenStreetMap",
    )

    # Add destination marker (large, always visible)
    if dest_coords:
        folium.Marker(
            location=[center_lat, center_lon],
            popup=folium.Popup(
                f"<div style='font-family:system-ui; font-size:14px;'>"
                f"<strong>{dest}</strong><br/>"
                f"<span style='color:#666;'>{trip.get('start_date', '')} → {trip.get('end_date', '')}</span>"
                f"</div>",
                max_width=280,
            ),
            tooltip=f"{dest} — Trip destination",
            icon=folium.Icon(color="red", icon="flag", prefix="glyphicon"),
        ).add_to(m)

    # Day filter
    day_filter = ["All Days"] + [f"Day {d.get('day_number', i+1)}" for i, d in enumerate(days)]
    choice = st.selectbox("Filter by day", day_filter, key="map_day_filter")
    day_idx = day_filter.index(choice) - 1 if choice != "All Days" else -1

    # Collect and add activity markers
    markers = _collect_markers(days, day_idx)
    has_item_markers = len(markers) > 0

    all_lats = [center_lat] if dest_coords else []
    all_lons = [center_lon] if dest_coords else []

    for di, day in enumerate(days):
        if day_idx >= 0 and di != day_idx:
            continue
        color = DAY_COLORS[di % len(DAY_COLORS)]
        day_num = day.get("day_number", di + 1)
        points = []

        for item in day.get("items") or []:
            lat = item.get("latitude")
            lon = item.get("longitude")
            if lat is not None and lon is not None:
                la, ln = float(lat), float(lon)
                points.append((la, ln))
                all_lats.append(la)
                all_lons.append(ln)

                item_type = item.get("item_type", "activity")
                icon_name = ITEM_TYPE_ICONS.get(item_type, "star")
                cost_str = f"₹{item.get('cost', 0):,.0f}" if item.get("cost", 0) > 0 else "Free"

                popup_html = (
                    f"<div style='font-family:system-ui; min-width:180px;'>"
                    f"<div style='font-size:13px; font-weight:600; margin-bottom:4px;'>"
                    f"Day {day_num} · {item.get('time', '')}</div>"
                    f"<div style='font-size:15px; font-weight:700; color:#1A5653; margin-bottom:4px;'>"
                    f"{item.get('title', '')}</div>"
                    f"<div style='font-size:12px; color:#666; margin-bottom:6px;'>"
                    f"{(item.get('description') or '')[:120]}</div>"
                    f"<div style='font-size:12px;'>"
                    f"<span style='background:#F0EDE6; padding:2px 6px; border-radius:3px;'>"
                    f"{item_type}</span> · {cost_str}</div>"
                    f"</div>"
                )

                folium.CircleMarker(
                    [la, ln],
                    radius=9,
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.85,
                    popup=folium.Popup(popup_html, max_width=300),
                    tooltip=f"Day {day_num}: {item.get('title', '')}",
                ).add_to(m)

        # Draw route line connecting activities within the same day
        if len(points) >= 2:
            folium.PolyLine(
                points, color=color, weight=3, opacity=0.6, dash_array="6,4",
            ).add_to(m)

    # Auto-fit bounds if we have multiple points
    if len(all_lats) >= 2:
        sw = [min(all_lats) - 0.01, min(all_lons) - 0.01]
        ne = [max(all_lats) + 0.01, max(all_lons) + 0.01]
        m.fit_bounds([sw, ne])

    # Show info if no activity markers have coordinates
    if not has_item_markers:
        st.caption(
            f"Showing {dest} on the map. Activity markers will appear when "
            f"activities with coordinates are available (via Google Places or location-aware search)."
        )

    # Day color legend
    if days and day_idx < 0:
        legend_parts = []
        for i, day in enumerate(days):
            c = DAY_COLORS[i % len(DAY_COLORS)]
            dn = day.get("day_number", i + 1)
            legend_parts.append(
                f"<span style='display:inline-flex; align-items:center; gap:4px; margin-right:12px;'>"
                f"<span style='width:10px; height:10px; border-radius:50%; background:{c}; display:inline-block;'></span>"
                f"<span style='font-size:0.78rem;'>Day {dn}</span></span>"
            )
        st.markdown(
            f"<div style='margin-top:6px;'>{''.join(legend_parts)}</div>",
            unsafe_allow_html=True,
        )

    st_folium(m, use_container_width=True, height=500, returned_objects=[])
