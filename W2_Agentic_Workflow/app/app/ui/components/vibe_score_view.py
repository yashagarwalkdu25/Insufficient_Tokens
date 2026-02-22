"""Vibe score view: editorial gauge, breakdown bars, matches, considerations."""
from __future__ import annotations

import streamlit as st
from typing import Any

try:
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False


def render_vibe_score(vibe_score: dict[str, Any] | None) -> None:
    if not vibe_score:
        st.info("Vibe score will appear after planning.")
        return

    score = vibe_score.get("overall_score", 0)
    tagline = vibe_score.get("tagline", "")
    breakdown = vibe_score.get("breakdown") or {}
    perfect = vibe_score.get("perfect_matches") or []
    considerations = vibe_score.get("considerations") or []

    col_gauge, col_detail = st.columns([1, 1.5])

    with col_gauge:
        if HAS_PLOTLY:
            fig = go.Figure(go.Indicator(
                mode="gauge",
                value=score,
                domain={"x": [0.15, 0.85], "y": [0.1, 0.6]},
                number={"font": {"family": "Cormorant Garamond", "size": 28, "color": "#1A5653"}},
                gauge={
                    "axis": {"range": [0, 100], "tickcolor": "#E8E2D8"},
                    "bar": {"color": "#1A5653", "thickness": 0.35},
                    "bgcolor": "#FAF6F0",
                    "borderwidth": 0,
                    "steps": [
                        {"range": [0, 33], "color": "rgba(196,77,77,0.12)"},
                        {"range": [33, 66], "color": "rgba(197,165,90,0.12)"},
                        {"range": [66, 100], "color": "rgba(45,139,95,0.12)"},
                    ],
                    "threshold": {"line": {"color": "#E8772E", "width": 3}, "value": 90},
                },
            ))
            fig.update_layout(
                height=220,
                margin=dict(l=20, r=20, t=20, b=20),
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Plus Jakarta Sans"),
                annotations=[
                    dict(
                        text=f"<b>{score}</b><br>/100",
                        x=0.5,
                        y=0.35,
                        xref="paper",
                        yref="paper",
                        showarrow=False,
                        font=dict(family="Cormorant Garamond", size=32, color="#1A5653"),
                        align="center",
                    ),
                ],
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.markdown(
                f'<div class="ts-vibe-ring">'
                f'<div class="ts-vibe-score">{score}</div>'
                f'<div class="ts-vibe-label">out of 100</div></div>',
                unsafe_allow_html=True,
            )

        if tagline:
            st.markdown(
                f'<p style="text-align:center; font-family:Cormorant Garamond,serif;'
                f' font-style:italic; font-size:1.1rem; color:var(--ts-text-muted);">'
                f'"{tagline}"</p>',
                unsafe_allow_html=True,
            )

    with col_detail:
        if breakdown:
            st.markdown("#### Breakdown")
            for name, val in breakdown.items():
                label = name.replace("_", " ").title()
                pct = min(max(val, 0), 100)
                color = "#2D8B5F" if pct >= 70 else "#C5A55A" if pct >= 40 else "#C44D4D"
                st.markdown(
                    f'<div style="margin:6px 0;">'
                    f'<div style="display:flex; justify-content:space-between; font-size:0.85rem;">'
                    f'<span>{label}</span><span style="font-weight:600;">{pct}%</span></div>'
                    f'<div style="background:var(--ts-border); border-radius:6px; height:8px; overflow:hidden;">'
                    f'<div style="background:{color}; width:{pct}%; height:100%; border-radius:6px;'
                    f' transition:width 0.6s ease;"></div></div></div>',
                    unsafe_allow_html=True,
                )

    if perfect:
        st.markdown("#### Perfect Matches")
        for p in perfect:
            st.markdown(
                f'<div style="padding:6px 12px; margin:4px 0; border-radius:8px;'
                f' background:rgba(45,139,95,0.08); border-left:3px solid var(--ts-success);'
                f' font-size:0.88rem;">{p}</div>',
                unsafe_allow_html=True,
            )

    if considerations:
        st.markdown("#### Considerations")
        for c in considerations:
            st.markdown(
                f'<div style="padding:6px 12px; margin:4px 0; border-radius:8px;'
                f' background:rgba(212,148,58,0.08); border-left:3px solid var(--ts-warning);'
                f' font-size:0.88rem;">{c}</div>',
                unsafe_allow_html=True,
            )
