"""Reasoning view: agent decision timeline with expandable details."""
from __future__ import annotations

import streamlit as st
from typing import Any


def render_reasoning(agent_decisions: list[dict[str, Any]]) -> None:
    if not agent_decisions:
        st.info("No agent decisions recorded yet.")
        return

    st.markdown("#### How TripSaathi planned your trip")
    st.caption("Each step shows the agent's reasoning, action taken, and performance.")

    for i, d in enumerate(agent_decisions):
        name = d.get("agent_name", "Agent").replace("_", " ").title()
        action = d.get("action", "") or "—"
        reasoning = d.get("reasoning", "")
        summary = d.get("result_summary", "")
        tokens = d.get("tokens_used", 0)
        latency = d.get("latency_ms", 0)

        label = f"{name}  ·  {action}" if action and action != "—" else name
        with st.expander(label, expanded=(i == 0)):
            if reasoning:
                st.markdown(
                    f'<div style="background:rgba(26,86,83,0.04); border-left:3px solid var(--ts-teal);'
                    f' padding:10px 14px; border-radius:8px; margin-bottom:8px; font-size:0.88rem; color:#1E2832;">'
                    f'<strong style="color:var(--ts-teal);">Reasoning</strong><br/>{reasoning}</div>',
                    unsafe_allow_html=True,
                )
            elif not summary and not (tokens or latency):
                st.markdown(
                    '<div style="background:rgba(26,86,83,0.04); border-left:3px solid var(--ts-teal);'
                    ' padding:10px 14px; border-radius:8px; font-size:0.88rem; color:#1E2832;">'
                    '<em>No reasoning or result recorded for this step.</em></div>',
                    unsafe_allow_html=True,
                )
            if summary:
                st.markdown(
                    f'<div style="background:rgba(197,165,90,0.06); border-left:3px solid var(--ts-gold);'
                    f' padding:10px 14px; border-radius:8px; font-size:0.88rem; color:#1E2832;">'
                    f'<strong style="color:#8B7330;">Result</strong><br/>{summary}</div>',
                    unsafe_allow_html=True,
                )
            if tokens or latency:
                st.caption(f"Tokens: {tokens:,}  ·  Latency: {latency:,} ms")
