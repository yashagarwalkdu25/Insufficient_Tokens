"""
Bundles View — AI Travel Negotiator UI component.

Renders three negotiated bundle cards (Budget Saver, Best Value, Experience Max)
with cost breakdowns, experience scores, trade-off bullets, and What-If controls.

Integrates with the main Streamlit flow before the itinerary is built.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional

import streamlit as st

from app.models.negotiation import BUNDLE_META

# ---------------------------------------------------------------------------
# CSS for bundle cards (injected once)
# ---------------------------------------------------------------------------

_BUNDLES_CSS = """
<style>
/* ── Full-bleed escape from Streamlit's 860px column ─────────── */
.nb-full-bleed {
  width: 100vw;
  margin-left: calc(-50vw + 50%);
  padding: 0 2rem;
  box-sizing: border-box;
}

/* ── Bundle card grid ─────────────────────────────────────────── */
.nb-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1.5rem;
  margin: 1rem 0 0;
  width: 100%;
  box-sizing: border-box;
}
@media (max-width: 900px) {
  .nb-grid { grid-template-columns: 1fr; }
}

.nb-card {
  background: var(--ts-surface);
  border: 2px solid var(--ts-border);
  border-radius: var(--ts-radius);
  padding: 2rem 2.2rem 2rem;
  box-shadow: var(--ts-shadow);
  transition: box-shadow 0.2s, border-color 0.2s, transform 0.15s;
  position: relative;
  cursor: default;
  min-width: 0;
  box-sizing: border-box;
}
.nb-card:hover {
  box-shadow: var(--ts-shadow-hover);
  transform: translateY(-2px);
}
.nb-card.nb-selected {
  border-color: var(--ts-saffron) !important;
  box-shadow: 0 0 0 3px rgba(107,63,160,0.18), var(--ts-shadow-hover);
}
.nb-badge {
  display: inline-block;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 0.22rem 0.75rem;
  border-radius: 20px;
  margin-bottom: 0.6rem;
}
.nb-title {
  font-family: var(--ts-font-display);
  font-size: 1.55rem;
  font-weight: 700;
  margin: 0.25rem 0 0.15rem;
  color: var(--ts-text);
}
.nb-summary {
  font-size: 0.88rem;
  color: var(--ts-text-muted);
  margin-bottom: 1rem;
  line-height: 1.5;
}
.nb-price {
  font-size: 2rem;
  font-weight: 700;
  color: var(--ts-teal);
  letter-spacing: -0.02em;
}
.nb-price-label {
  font-size: 0.78rem;
  color: var(--ts-text-muted);
  margin-bottom: 1rem;
}
.nb-scores {
  display: flex;
  gap: 0.75rem;
  margin-bottom: 1rem;
}
.nb-score-pill {
  flex: 1;
  text-align: center;
  background: var(--ts-cream);
  border-radius: 8px;
  padding: 0.45rem 0.25rem;
}
.nb-score-val {
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--ts-saffron);
}
.nb-score-lbl {
  font-size: 0.68rem;
  color: var(--ts-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.nb-divider {
  border: none;
  border-top: 1px solid var(--ts-border);
  margin: 0.85rem 0;
}
.nb-detail-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  font-size: 0.85rem;
  padding: 0.28rem 0;
  gap: 0.5rem;
}
.nb-detail-label {
  color: var(--ts-text-muted);
  flex-shrink: 1;
  min-width: 0;
  word-break: break-word;
}
.nb-detail-value {
  color: var(--ts-text);
  font-weight: 500;
  text-align: right;
}
.nb-activity-chip {
  display: inline-block;
  background: var(--ts-cream);
  border-radius: 6px;
  padding: 0.18rem 0.55rem;
  font-size: 0.78rem;
  color: var(--ts-text-muted);
  margin: 0.15rem 0.2rem 0.15rem 0;
}
.nb-tradeoff-list {
  list-style: none;
  padding: 0;
  margin: 0 0 0.9rem;
}
.nb-tradeoff-list li {
  font-size: 0.85rem;
  padding: 0.26rem 0;
  display: flex;
  gap: 0.45rem;
  align-items: flex-start;
}
.nb-gain { color: var(--ts-success); }
.nb-sacrifice { color: var(--ts-warning); }
.nb-breakdown-row {
  display: flex;
  justify-content: space-between;
  font-size: 0.82rem;
  padding: 0.14rem 0;
  color: var(--ts-text-muted);
}
.nb-breakdown-row.nb-total {
  font-weight: 700;
  color: var(--ts-text);
  border-top: 1px solid var(--ts-border);
  margin-top: 0.35rem;
  padding-top: 0.35rem;
}
.nb-rejected {
  font-size: 0.78rem;
  color: var(--ts-text-muted);
  margin-top: 0.5rem;
}
.nb-rejected span {
  font-style: italic;
}
/* What-If bar */
.nb-whatif-bar {
  background: var(--ts-cream);
  border: 1px solid var(--ts-border);
  border-radius: var(--ts-radius);
  padding: 1rem 1.2rem;
  margin-bottom: 1.2rem;
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}
.nb-whatif-label {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--ts-text);
  flex-shrink: 0;
}
/* Decision log */
.nb-log {
  background: var(--ts-cream);
  border-left: 3px solid var(--ts-saffron);
  border-radius: 0 8px 8px 0;
  padding: 0.7rem 1rem;
  font-size: 0.78rem;
  color: var(--ts-text-muted);
  font-family: monospace;
  max-height: 200px;
  overflow-y: auto;
  margin-top: 0.5rem;
}
.nb-log p { margin: 0.15rem 0; }
</style>
"""

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

_BADGE_COLOURS: Dict[str, Dict[str, str]] = {
    "budget_saver":   {"bg": "#E8F5EE", "fg": "#2D8B5F"},
    "best_value":     {"bg": "#E8EEF8", "fg": "#1E3A6E"},
    "experience_max": {"bg": "#F0EAF8", "fg": "#6B3FA0"},
}


def _score_bar_html(label: str, value: int, colour: str = "#6B3FA0") -> str:
    pct = max(0, min(100, value))
    return f"""
<div style="margin-bottom:0.3rem;">
  <div style="display:flex;justify-content:space-between;font-size:0.72rem;color:var(--ts-text-muted);margin-bottom:2px;">
    <span>{label}</span><span style="font-weight:600;color:{colour};">{pct}</span>
  </div>
  <div style="background:var(--ts-border);border-radius:4px;height:5px;">
    <div style="background:{colour};width:{pct}%;height:5px;border-radius:4px;transition:width 0.4s;"></div>
  </div>
</div>"""


def _booking_links_html(links: Dict[str, Optional[str]]) -> str:
    items = []
    for key, url in links.items():
        if url:
            label = key.replace("_", " ").title()
            items.append(f'<a href="{url}" target="_blank" style="font-size:0.75rem;color:var(--ts-teal-light);margin-right:0.8rem;">Book {label} ↗</a>')
    return "".join(items) if items else '<span style="font-size:0.75rem;color:var(--ts-text-muted);">No booking links available</span>'


# ---------------------------------------------------------------------------
# Bundle card — pure HTML (no interactive widgets inside)
# ---------------------------------------------------------------------------

def _bundle_card_html(bundle: Dict[str, Any], is_selected: bool) -> str:
    """Return the full HTML string for one bundle card."""
    bid = bundle.get("id", "")
    meta = BUNDLE_META.get(bid, {"title": bid, "summary": "", "icon": "📦", "color": "#1E3A6E"})  # type: ignore[arg-type]
    badge_col = _BADGE_COLOURS.get(bid, {"bg": "#EEE", "fg": "#333"})
    breakdown = bundle.get("breakdown") or {}
    tradeoffs = bundle.get("tradeoffs") or []
    booking_links = bundle.get("booking_links") or {}

    exp_score = bundle.get("experience_score", 0)
    cost_score = bundle.get("cost_score", 0)
    conv_score = bundle.get("convenience_score", 0)
    final_score = bundle.get("final_score", 0)
    total = breakdown.get("total", 0)

    selected_class = "nb-selected" if is_selected else ""
    transport = bundle.get("transport") or {}
    stay = bundle.get("stay") or {}
    activities = bundle.get("activities") or []

    t_name = transport.get("operator") or transport.get("name") or "Transport"
    t_type = (transport.get("transport_type") or "").title()
    t_price = transport.get("price") or transport.get("cost") or 0
    t_duration = transport.get("duration") or transport.get("duration_hours") or ""
    s_name = stay.get("name") or "Stay"
    s_stars = float(stay.get("star_rating") or 0)
    s_price = stay.get("price_per_night") or stay.get("price") or stay.get("cost") or 0
    s_nights = stay.get("nights") or ""

    selected_badge = (
        "<span style='float:right;font-size:0.78rem;background:var(--ts-saffron);"
        "color:#fff;padding:0.18rem 0.7rem;border-radius:12px;font-weight:600;'>Selected ✓</span>"
        if is_selected else ""
    )

    tradeoff_rows = "".join(
        f'<li><span class="nb-gain">✓ {t["gain"]}</span></li>'
        f'<li><span class="nb-sacrifice">✗ {t["sacrifice"]}</span></li>'
        for t in tradeoffs[:3]
    )

    # Transport detail row
    t_detail_parts = [t_name]
    if t_type:
        t_detail_parts.append(t_type)
    if t_duration:
        t_detail_parts.append(f"{t_duration}h")
    t_detail_str = " · ".join(t_detail_parts)
    t_price_str = f"₹{t_price:,.0f}" if t_price else "—"

    # Stay detail row
    s_detail_parts = [s_name, f"{s_stars:.1f}★"]
    if s_nights:
        s_detail_parts.append(f"{s_nights} nights")
    s_detail_str = " · ".join(s_detail_parts)
    s_price_str = f"₹{s_price:,.0f}/night" if s_price else "—"

    # Activities chips (up to 4)
    activity_chips = "".join(
        f'<span class="nb-activity-chip">{a.get("name", "?")}</span>'
        for a in activities[:4]
    )
    if len(activities) > 4:
        activity_chips += f'<span class="nb-activity-chip">+{len(activities) - 4} more</span>'

    # Breakdown rows for inline display
    breakdown_html = "".join(
        f'<div class="nb-breakdown-row"><span>{lbl}</span><span>₹{breakdown.get(key, 0):,.0f}</span></div>'
        for lbl, key in [("Transport", "transport"), ("Stay", "stay"),
                         ("Activities", "activities"), ("Food", "food"), ("Buffer", "buffer")]
        if breakdown.get(key, 0)
    )
    breakdown_html += (
        f'<div class="nb-breakdown-row nb-total"><span>Total</span>'
        f'<span>₹{total:,.0f}</span></div>'
    )

    return f"""
<div class="nb-card {selected_class}">
  <div style="overflow:hidden;">
    <span class="nb-badge" style="background:{badge_col['bg']};color:{badge_col['fg']};">
      {meta['icon']} {meta['title']}
    </span>
    {selected_badge}
  </div>
  <div class="nb-title">{meta['title']}</div>
  <div class="nb-summary">{meta['summary']}</div>
  <div class="nb-price">₹{total:,.0f}</div>
  <div class="nb-price-label">total estimated cost</div>

  <div class="nb-scores">
    <div class="nb-score-pill">
      <div class="nb-score-val" style="color:#6B3FA0;">{exp_score}</div>
      <div class="nb-score-lbl">Experience</div>
    </div>
    <div class="nb-score-pill">
      <div class="nb-score-val" style="color:#2D8B5F;">{cost_score}</div>
      <div class="nb-score-lbl">Cost</div>
    </div>
    <div class="nb-score-pill">
      <div class="nb-score-val" style="color:#1E3A6E;">{conv_score}</div>
      <div class="nb-score-lbl">Convenience</div>
    </div>
    <div class="nb-score-pill">
      <div class="nb-score-val" style="color:#D4943A;">{final_score:.0f}</div>
      <div class="nb-score-lbl">Overall</div>
    </div>
  </div>

  <hr class="nb-divider"/>

  <div class="nb-detail-row">
    <span class="nb-detail-label">✈ {t_detail_str}</span>
    <span class="nb-detail-value">{t_price_str}</span>
  </div>
  <div class="nb-detail-row">
    <span class="nb-detail-label">🏨 {s_detail_str}</span>
    <span class="nb-detail-value">{s_price_str}</span>
  </div>
  <div style="margin: 0.5rem 0 0.2rem;">
    <span style="font-size:0.78rem;color:var(--ts-text-muted);font-weight:600;text-transform:uppercase;letter-spacing:0.05em;">🎯 Activities</span>
    <div style="margin-top:0.35rem;">{activity_chips if activity_chips else '<span style="font-size:0.82rem;color:var(--ts-text-muted);">None included</span>'}</div>
  </div>

  <hr class="nb-divider"/>

  <div style="margin-bottom:0.6rem;">{breakdown_html}</div>

  <hr class="nb-divider"/>

  <ul class="nb-tradeoff-list">{tradeoff_rows}</ul>

  <div style="margin-top:0.7rem;">{_booking_links_html(booking_links)}</div>
</div>"""


# ---------------------------------------------------------------------------
# Full-width grid of all bundle cards + interactive controls per card
# ---------------------------------------------------------------------------


def _widen_next_columns(marker_id: str, width: str = "100vw", offset: str = "calc(-50vw + 50%)") -> None:
    """Inject JS that widens the next st.columns block after a marker div."""
    import streamlit.components.v1 as _stc
    _stc.html(f"""<script>
(function(){{
  function run() {{
    try {{
      var doc = window.parent.document;
      var marker = doc.getElementById('{marker_id}');
      if (!marker) return;
      var node = marker;
      for (var i = 0; i < 8; i++) {{
        node = node.parentElement;
        if (!node) break;
        var sib = node.nextElementSibling;
        if (!sib) continue;
        var hb = sib.matches('[data-testid="stHorizontalBlock"]') ? sib
               : sib.querySelector('[data-testid="stHorizontalBlock"]');
        if (hb) {{
          hb.style.setProperty('width', '{width}', 'important');
          hb.style.setProperty('margin-left', '{offset}', 'important');
          hb.style.setProperty('padding', '0 2rem', 'important');
          hb.style.setProperty('box-sizing', 'border-box', 'important');
          return;
        }}
      }}
    }} catch(e) {{}}
  }}
  run(); setTimeout(run, 80); setTimeout(run, 300); setTimeout(run, 800);
}})();
</script>""", height=0)


def _render_bundle_cards_grid(
    bundles: List[Dict[str, Any]],
    selected_id: Optional[str],
    on_select: Callable[[str], None],
) -> None:
    """
    Cards — full-bleed HTML grid.
    Buttons + expanders — st.columns rows, each widened to match via JS.
    """
    # ── Cards HTML ─────────────────────────────────────────────────────────
    cards_html = "".join(
        _bundle_card_html(bundle, bundle.get("id") == selected_id)
        for bundle in bundles
    )
    st.markdown(
        f'<div class="nb-full-bleed"><div class="nb-grid">{cards_html}</div></div>',
        unsafe_allow_html=True,
    )

    # ── Select buttons row ─────────────────────────────────────────────────
    st.markdown('<div id="nb-btn-marker"></div>', unsafe_allow_html=True)
    _widen_next_columns("nb-btn-marker", "100vw", "calc(-50vw + 50%)")
    btn_cols = st.columns(len(bundles), gap="large")
    for i, bundle in enumerate(bundles):
        bid = bundle.get("id", "")
        meta = BUNDLE_META.get(bid, {"title": bid, "icon": "📦"})  # type: ignore[arg-type]
        is_selected = bid == selected_id
        with btn_cols[i]:
            btn_label = "✓ Selected" if is_selected else f"Select {meta['title']}"
            if st.button(btn_label, key=f"select_bundle_{bid}",
                         disabled=is_selected, use_container_width=True):
                on_select(bid)

    # ── Expanders row ──────────────────────────────────────────────────────
    st.markdown('<div id="nb-exp-marker"></div>', unsafe_allow_html=True)
    _widen_next_columns("nb-exp-marker", "100vw", "calc(-50vw + 50%)")
    exp_cols = st.columns(len(bundles), gap="large")
    for i, bundle in enumerate(bundles):
        bid = bundle.get("id", "")
        breakdown = bundle.get("breakdown") or {}
        tradeoffs = bundle.get("tradeoffs") or []
        activities = bundle.get("activities") or []
        rejected = bundle.get("rejected") or []
        decision_log = bundle.get("decision_log") or []
        exp_score = bundle.get("experience_score", 0)
        cost_score = bundle.get("cost_score", 0)
        conv_score = bundle.get("convenience_score", 0)
        with exp_cols[i]:
            with st.expander("Full details & decision log", expanded=False):
                st.markdown("**Score Breakdown**")
                st.markdown(
                    _score_bar_html("Experience", exp_score, "#6B3FA0")
                    + _score_bar_html("Cost Efficiency", cost_score, "#2D8B5F")
                    + _score_bar_html("Convenience", conv_score, "#1E3A6E"),
                    unsafe_allow_html=True,
                )
                if tradeoffs:
                    st.markdown("**All Trade-offs**")
                    for t in tradeoffs:
                        st.markdown(f"- ✓ **{t['gain']}** / ✗ {t['sacrifice']}")
                if activities:
                    st.markdown("**All Activities**")
                    for a in activities:
                        price_str = f"₹{a.get('price', 0):,.0f}" if a.get("price") else "Free"
                        st.markdown(
                            f"- {a.get('name', '?')} "
                            f"({a.get('category', '?')}, {a.get('duration_hours', '?')}h)"
                            f" — {price_str}"
                        )
                if rejected:
                    st.markdown("**Rejected Alternatives**")
                    for r in rejected:
                        st.markdown(f"- ~~{r['name']}~~ — {r['reason']}")
                if decision_log:
                    st.markdown("**Decision Log**")
                    log_html = "".join(f"<p>› {line}</p>" for line in decision_log)
                    st.markdown(f'<div class="nb-log">{log_html}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# What-If bar
# ---------------------------------------------------------------------------

def _render_whatif_bar(
    current_delta: int,
    on_apply: Callable[[int], None],
) -> None:
    st.markdown("### What-If Budget Adjustments")
    st.markdown(
        '<div class="nb-whatif-bar">'
        '<span class="nb-whatif-label">🔄 Adjust budget:</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 2])
    with col1:
        if st.button("−₹10,000", key="wi_minus_10k", use_container_width=True):
            on_apply(-10000)
    with col2:
        if st.button("−₹5,000", key="wi_minus_5k", use_container_width=True):
            on_apply(-5000)
    with col3:
        if st.button("+₹5,000", key="wi_plus_5k", use_container_width=True):
            on_apply(5000)
    with col4:
        if st.button("+₹10,000", key="wi_plus_10k", use_container_width=True):
            on_apply(10000)
    with col5:
        custom = st.number_input(
            "Custom delta (₹)",
            value=0,
            step=1000,
            key="wi_custom_delta",
            label_visibility="collapsed",
        )
        if st.button("Apply custom", key="wi_apply_custom", use_container_width=True):
            if custom != 0:
                on_apply(int(custom))

    if current_delta != 0:
        direction = "+" if current_delta > 0 else ""
        st.caption(f"Current budget adjustment: {direction}₹{current_delta:,}")

    # Natural language parser
    st.markdown("**Or type a what-if:**")
    nl_input = st.text_input(
        "e.g. 'what if I increase budget by 5000'",
        key="wi_nl_input",
        label_visibility="collapsed",
        placeholder="what if I increase budget by 5000?",
    )
    if st.button("Apply", key="wi_nl_apply"):
        parsed = _parse_whatif_nl(nl_input)
        if parsed is not None:
            on_apply(parsed)
        else:
            st.warning("Could not parse budget adjustment. Try: 'increase by 5000' or 'reduce by 3000'")


def _parse_whatif_nl(text: str) -> Optional[int]:
    """Parse natural language what-if requests into a delta integer."""
    if not text:
        return None
    text = text.lower().strip()
    # Match patterns like "increase by 5000", "reduce by 3000", "+5000", "-2000"
    patterns = [
        (r"(?:increase|add|more|up|raise|higher)\s+(?:by\s+)?(?:rs\.?|₹|inr)?\s*(\d[\d,]*)", +1),
        (r"(?:decrease|reduce|less|down|lower|cut|save)\s+(?:by\s+)?(?:rs\.?|₹|inr)?\s*(\d[\d,]*)", -1),
        (r"[+]\s*(?:rs\.?|₹|inr)?\s*(\d[\d,]*)", +1),
        (r"[-]\s*(?:rs\.?|₹|inr)?\s*(\d[\d,]*)", -1),
        (r"(?:rs\.?|₹|inr)\s*(\d[\d,]*)", +1),  # bare amount → assume increase
    ]
    for pattern, sign in patterns:
        m = re.search(pattern, text)
        if m:
            amount_str = m.group(1).replace(",", "")
            try:
                return sign * int(amount_str)
            except ValueError:
                continue
    return None


# ---------------------------------------------------------------------------
# Main render function
# ---------------------------------------------------------------------------

def render_bundles_view(
    state: Dict[str, Any],
    on_bundle_selected: Callable[[str], None],
    on_whatif: Callable[[int], None],
) -> None:
    """
    Render the full AI Travel Negotiator panel.

    Args:
        state: Current TravelPlannerState dict.
        on_bundle_selected: Callback when user clicks "Select this bundle".
                            Receives bundle_id string.
        on_whatif: Callback when user applies a what-if budget adjustment.
                   Receives delta_budget integer.
    """
    # Inject component CSS
    st.markdown(_BUNDLES_CSS, unsafe_allow_html=True)

    bundles: List[Dict[str, Any]] = state.get("bundles") or []
    selected_id: Optional[str] = state.get("selected_bundle_id")
    current_delta: int = int(state.get("what_if_delta") or 0)
    negotiation_log: List[str] = state.get("negotiation_log") or []
    feasibility_issues: List[str] = state.get("feasibility_issues") or []

    # Header
    st.markdown("""
<div style="display:flex;align-items:center;gap:0.8rem;margin-bottom:0.3rem;">
  <span style="font-size:1.8rem;">🤝</span>
  <div>
    <h2 style="margin:0;font-family:var(--ts-font-display);font-size:1.7rem;">AI Travel Negotiator</h2>
    <p style="margin:0;color:var(--ts-text-muted);font-size:0.85rem;">Three negotiated bundles — pick the one that fits your style.</p>
  </div>
</div>
""", unsafe_allow_html=True)

    st.markdown('<div class="ts-separator"></div>', unsafe_allow_html=True)

    if not bundles:
        st.info("Bundles are being generated... Run the planning flow to see negotiated options.")
        return

    # Feasibility warnings
    if feasibility_issues:
        with st.expander(f"⚠️ {len(feasibility_issues)} feasibility issue(s) auto-resolved", expanded=False):
            for issue in feasibility_issues:
                st.caption(f"• {issue}")

    # What-If bar
    _render_whatif_bar(current_delta, on_whatif)

    st.markdown('<div class="ts-separator"></div>', unsafe_allow_html=True)

    # Bundle cards — full-bleed HTML grid so cards are never cramped
    st.markdown("### Choose Your Bundle")
    _render_bundle_cards_grid(bundles, selected_id, on_bundle_selected)

    # Negotiation transparency log
    if negotiation_log:
        with st.expander("📋 Negotiation Decision Log", expanded=False):
            st.markdown("*How the AI Negotiator chose these bundles:*")
            log_html = "".join(f"<p>› {line}</p>" for line in negotiation_log[-20:])
            st.markdown(f'<div class="nb-log">{log_html}</div>', unsafe_allow_html=True)

    # What-if history
    what_if_history = state.get("what_if_history") or []
    if what_if_history:
        with st.expander(f"🔄 What-If History ({len(what_if_history)} adjustments)", expanded=False):
            for i, wif in enumerate(what_if_history):
                delta = wif.get("delta_budget", 0)
                direction = "increased" if delta > 0 else "decreased"
                st.caption(f"{i+1}. Budget {direction} by ₹{abs(delta):,}")

    st.markdown('<div class="ts-separator"></div>', unsafe_allow_html=True)

    # Proceed button
    if selected_id:
        selected_meta = BUNDLE_META.get(selected_id, {})  # type: ignore[arg-type]
        st.success(f"Bundle selected: **{selected_meta.get('title', selected_id)}** — click 'Build Itinerary' to continue.")
        if st.button("Build Itinerary →", type="primary", key="bundles_proceed_btn", use_container_width=False):
            st.session_state["bundles_proceed"] = True
            st.rerun()
    else:
        st.info("Select a bundle above to proceed to itinerary building.")
