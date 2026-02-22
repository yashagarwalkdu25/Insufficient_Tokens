"""Local tips view: tips, hidden gems, events with card-based layout."""
from __future__ import annotations

import streamlit as st
from typing import Any


def render_local_tips(
    tips: list[dict[str, Any]],
    gems: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> None:
    tcol, gcol, ecol = st.columns(3)

    with tcol:
        st.markdown("### Local Tips")
        if not tips:
            st.caption("No local tips yet.")
        for t in tips[:10]:
            title = t.get("title", "")
            content = (t.get("content") or "")[:200]
            cat = t.get("category", "")
            source = t.get("source_platform", "")
            st.markdown(
                f'<div class="ts-tip-card">'
                f'<strong>{title}</strong>'
                f'<br/><span style="font-size:0.82rem; color:var(--ts-text-muted);">{content}</span>'
                f'<br/><span class="ts-pill" style="font-size:0.72rem; padding:2px 8px; margin-top:6px;">{cat}</span>'
                + (f' <span style="font-size:0.72rem; color:var(--ts-text-muted);">via {source}</span>' if source else '')
                + f'</div>',
                unsafe_allow_html=True,
            )

    with gcol:
        st.markdown("### Hidden Gems")
        if not gems:
            st.caption("No hidden gems discovered yet.")
        for g in gems[:8]:
            name = g.get("name", "")
            why = g.get("why_special", "")
            pro = g.get("pro_tip", "")
            conf = g.get("confidence", 1)
            conf_pct = int(conf * 100) if isinstance(conf, float) and conf <= 1 else int(conf)
            st.markdown(
                f'<div class="ts-tip-card ts-gem-card">'
                f'<strong>{name}</strong>'
                f'<br/><span style="font-size:0.82rem; color:var(--ts-text-muted);">{why}</span>'
                + (f'<br/><em style="font-size:0.82rem; color:var(--ts-gold);">Pro tip: {pro}</em>' if pro else '')
                + f'<br/><div style="background:var(--ts-border); border-radius:10px; height:6px; margin-top:6px;">'
                f'<div style="background:var(--ts-gold); width:{conf_pct}%; height:100%; border-radius:10px;"></div></div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    with ecol:
        st.markdown("### Events & Festivals")
        if not events:
            st.caption("No events in this period.")
        for e in events[:8]:
            name = e.get("name", "")
            impact = e.get("impact", "neutral")
            rec = e.get("recommendation", "")
            cls = f"ts-event-{impact}" if impact in ("positive", "neutral", "negative") else "ts-event-neutral"
            badge = {"positive": "🟢", "neutral": "🟡", "negative": "🔴"}.get(impact, "🟡")
            st.markdown(
                f'<div class="ts-tip-card {cls}">'
                f'{badge} <strong>{name}</strong>'
                f'<br/><span style="font-size:0.82rem; color:var(--ts-text-muted);">{rec}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
