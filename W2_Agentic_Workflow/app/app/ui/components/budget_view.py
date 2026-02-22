"""Budget view: metric boxes, category pie, daily bar chart."""
from __future__ import annotations

import streamlit as st
from typing import Any

try:
    import plotly.express as px
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

BRAND_COLORS = ["#1A5653", "#E8772E", "#C5A55A", "#2A7A76", "#F09A5B", "#7A8B8A", "#2D8B5F", "#C44D4D"]


def render_budget(budget_tracker: dict[str, Any] | None, state: dict[str, Any]) -> None:
    if not budget_tracker:
        req = state.get("trip_request") or {}
        total = req.get("budget") or 0
        st.metric("Total budget", f"₹{total:,.0f}")
        st.info("Budget breakdown will appear after planning.")
        return

    total_budget = budget_tracker.get("total_budget") or 0
    categories = budget_tracker.get("categories") or []
    warnings = budget_tracker.get("warnings") or []

    spent = sum(c.get("spent", 0) for c in categories)
    remaining = total_budget - spent

    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown(
            f'<div class="ts-metric-box"><div class="ts-metric-value">₹{total_budget:,.0f}</div>'
            f'<div class="ts-metric-label">Total budget</div></div>',
            unsafe_allow_html=True,
        )
    with m2:
        st.markdown(
            f'<div class="ts-metric-box"><div class="ts-metric-value" style="color:var(--ts-saffron);">₹{spent:,.0f}</div>'
            f'<div class="ts-metric-label">Estimated spend</div></div>',
            unsafe_allow_html=True,
        )
    with m3:
        color = "var(--ts-success)" if remaining >= 0 else "var(--ts-danger)"
        st.markdown(
            f'<div class="ts-metric-box"><div class="ts-metric-value" style="color:{color};">₹{remaining:,.0f}</div>'
            f'<div class="ts-metric-label">Remaining</div></div>',
            unsafe_allow_html=True,
        )

    for w in warnings:
        st.warning(w)

    if HAS_PLOTLY and categories:
        ch1, ch2 = st.columns(2)
        with ch1:
            names = [c.get("category", "?").replace("_", " ").title() for c in categories]
            values = [c.get("spent", 0) for c in categories]
            fig = px.pie(
                names=names, values=values,
                color_discrete_sequence=BRAND_COLORS,
                hole=0.45,
            )
            fig.update_layout(
                showlegend=True,
                legend=dict(orientation="h", y=-0.1),
                margin=dict(l=10, r=10, t=30, b=10),
                height=300,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Plus Jakarta Sans"),
            )
            fig.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig, use_container_width=True)

        with ch2:
            trip = state.get("trip") or {}
            days = trip.get("days") or []
            if days:
                day_labels = [f"Day {d.get('day_number')}" for d in days]
                day_costs = [d.get("day_cost", 0) for d in days]
                fig2 = go.Figure(data=[go.Bar(
                    x=day_labels, y=day_costs,
                    marker_color=BRAND_COLORS[:len(days)],
                    marker_line_width=0,
                )])
                fig2.update_layout(
                    xaxis_title="", yaxis_title="₹",
                    margin=dict(l=10, r=10, t=30, b=10),
                    height=300,
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(family="Plus Jakarta Sans"),
                )
                fig2.update_xaxes(showgrid=False)
                fig2.update_yaxes(showgrid=True, gridcolor="#E8E2D8")
                st.plotly_chart(fig2, use_container_width=True)
