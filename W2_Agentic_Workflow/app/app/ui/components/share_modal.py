"""Share modal: PDF/HTML/PPT download, QR code, shareable link."""
from __future__ import annotations

import streamlit as st
from typing import Any


def render_share_modal(state: dict[str, Any], base_url: str = "http://localhost:8501") -> None:
    try:
        from app.export.qr_generator import generate_trip_qr
        from app.export.html_exporter import export_to_html
        from app.database import save_shared_trip, generate_short_id
    except ImportError:
        st.warning("Export module not available.")
        return

    trip_id = st.session_state.get("shared_trip_id")
    if not trip_id:
        trip_id = generate_short_id()
        save_shared_trip(trip_id, state)
        st.session_state["shared_trip_id"] = trip_id
    share_url = f"{base_url}/?id={trip_id}"

    # Card header — rendered as a single HTML block (Streamlit can't wrap widgets in divs)
    st.markdown(
        '<div class="ts-share-card">'
        '<h3 style="margin:0 0 0.3rem 0;">Share your journey</h3>'
        '<p style="margin:0 0 0.8rem 0; color:var(--ts-text-muted); font-size:0.9rem;">'
        "Send this link to anyone — they'll see your full itinerary.</p>"
        f'<div class="ts-share-url">{share_url}</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    if st.button("Copy link", key="copy_link_btn"):
        st.success("Copy the link above (Ctrl+C / Cmd+C)")

    try:
        qr_bytes = generate_trip_qr(trip_id, base_url)
        if qr_bytes:
            st.image(qr_bytes, caption="Scan to open trip", width=180)
    except Exception:
        pass

    st.markdown('<div class="ts-separator"></div>', unsafe_allow_html=True)
    st.markdown("#### Download")
    try:
        from app.export.pdf_generator import PDFGenerator
        gen = PDFGenerator()
        pdf_bytes = gen.generate_pdf(
            state.get("trip") or {},
            state,
            state.get("vibe_score") or {},
            state.get("budget_tracker") or {},
        )
        st.download_button(
            "Download PDF",
            data=pdf_bytes,
            file_name="tripsaathi_itinerary.pdf",
            mime="application/pdf",
            key="dl_pdf",
            use_container_width=True,
        )
    except Exception as e:
        st.caption(f"PDF: {str(e)[:50]}")
