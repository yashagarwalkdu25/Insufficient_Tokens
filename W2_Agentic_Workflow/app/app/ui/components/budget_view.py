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

BRAND_COLORS = ["#1E3A6E", "#6B3FA0", "#7B5CB8", "#2E55A0", "#8B60C0", "#A08FD0", "#2D8B5F", "#C44D4D"]
CHART_FONT = dict(color="#1A1D3A", family="Plus Jakarta Sans, system-ui, sans-serif")


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
            allocated = [c.get("allocated", 0) for c in categories]
            actual    = [c.get("spent", 0) for c in categories]

            # Use allocated budget for the pie — actual spend is often 0 for meals/misc
            # but fall back to allocated when all actuals are zero
            use_values = actual if any(v > 0 for v in actual) else allocated
            pie_label  = "Actual Spend" if any(v > 0 for v in actual) else "Budget Allocation"

            # Always blend: show allocated slice but shade by actual if available
            # Build combined: use allocated as base, overlay actual where non-zero
            pie_names  = names
            pie_values = [a if a > 0 else al for a, al in zip(actual, allocated)]

            fig = px.pie(
                names=pie_names, values=pie_values,
                color_discrete_sequence=BRAND_COLORS,
                hole=0.45,
                title=pie_label,
            )
            fig.update_layout(
                showlegend=True,
                legend=dict(orientation="h", y=-0.15, font=dict(color="#1A1D3A")),
                margin=dict(l=10, r=10, t=40, b=10),
                height=320,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=CHART_FONT,
                title_font=dict(color="#1A1D3A", size=13),
            )
            fig.update_traces(
                textposition="inside",
                textinfo="percent+label",
                textfont=dict(color="#FFFFFF"),
                hovertemplate="<b>%{label}</b><br>₹%{value:,.0f}<br>%{percent}<extra></extra>",
            )
            st.plotly_chart(fig, use_container_width=True)

        with ch2:
            trip = state.get("trip") or {}
            days = trip.get("days") or []
            cat_names = [c.get("category", "?").replace("_", " ").title() for c in categories]
            cat_alloc  = [c.get("allocated", 0) for c in categories]
            cat_spent  = [c.get("spent", 0) for c in categories]

            fig2 = go.Figure()
            fig2.add_trace(go.Bar(
                name="Allocated",
                x=cat_names, y=cat_alloc,
                marker_color="#A08FD0",
                marker_line_width=0,
            ))
            fig2.add_trace(go.Bar(
                name="Spent",
                x=cat_names, y=cat_spent,
                marker_color="#1E3A6E",
                marker_line_width=0,
            ))
            fig2.update_layout(
                barmode="group",
                xaxis_title="", yaxis_title="₹",
                margin=dict(l=10, r=10, t=40, b=10),
                height=320,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=CHART_FONT,
                legend=dict(font=dict(color="#1A1D3A"), orientation="h", y=-0.2),
                title=dict(text="Allocated vs Spent", font=dict(color="#1A1D3A", size=13)),
            )
            fig2.update_xaxes(showgrid=False, tickfont=dict(color="#1A1D3A"))
            fig2.update_yaxes(showgrid=True, gridcolor="#DDD5EF", tickfont=dict(color="#1A1D3A"))
            st.plotly_chart(fig2, use_container_width=True)

            # Day-by-day cost bar if trip has days
            if days:
                day_labels = [f"Day {d.get('day_number')}" for d in days]
                day_costs  = [d.get("day_cost", 0) for d in days]
                fig3 = go.Figure(data=[go.Bar(
                    x=day_labels, y=day_costs,
                    marker_color=BRAND_COLORS[:len(days)],
                    marker_line_width=0,
                    hovertemplate="<b>%{x}</b><br>₹%{y:,.0f}<extra></extra>",
                )])
                fig3.update_layout(
                    xaxis_title="", yaxis_title="₹",
                    margin=dict(l=10, r=10, t=40, b=10),
                    height=260,
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=CHART_FONT,
                    title=dict(text="Cost per Day", font=dict(color="#1A1D3A", size=13)),
                )
                fig3.update_xaxes(showgrid=False, tickfont=dict(color="#1A1D3A"))
                fig3.update_yaxes(showgrid=True, gridcolor="#DDD5EF", tickfont=dict(color="#1A1D3A"))
                st.plotly_chart(fig3, use_container_width=True)
