"""Streamlit UI for the Agentic RAG News Claim Verifier."""
import streamlit as st
import time
from agent import ClaimVerifier, VerificationResult
from seed_kb import seed
from vector_store import VectorStore

# ── Page config ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="Claim Verifier — Agentic RAG",
    page_icon="🔍",
    layout="wide",
)

# ── Custom CSS ────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* ── Global ───────────────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    .block-container {
        padding-top: 2rem !important;
        max-width: 1100px !important;
    }

    /* ── Hide default Streamlit header/footer ──── */
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}

    /* ── Hero Section ─────────────────────────────── */
    .hero {
        text-align: center;
        padding: 2.5rem 1rem 1.5rem;
        margin-bottom: 1rem;
    }
    .hero-icon {
        font-size: 2.8rem;
        margin-bottom: 0.3rem;
        display: inline-block;
        animation: pulse-glow 2.5s ease-in-out infinite;
    }
    @keyframes pulse-glow {
        0%, 100% { filter: drop-shadow(0 0 6px rgba(99,102,241,0.4)); transform: scale(1); }
        50% { filter: drop-shadow(0 0 18px rgba(99,102,241,0.7)); transform: scale(1.08); }
    }
    .hero h1 {
        font-size: 2.2rem;
        font-weight: 800;
        letter-spacing: -0.5px;
        margin: 0 0 0.3rem;
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a855f7 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .hero p {
        font-size: 1rem;
        color: var(--text-color, #94a3b8);
        opacity: 0.6;
        margin: 0;
        font-weight: 400;
    }

    /* ── Input Area ───────────────────────────────── */
    .stTextArea textarea {
        border-radius: 14px !important;
        border: 2px solid rgba(128,128,128,0.3) !important;
        padding: 16px !important;
        font-size: 1rem !important;
        transition: border-color 0.3s, box-shadow 0.3s !important;
        background: var(--secondary-background-color, #f8fafc) !important;
        color: var(--text-color, #334155) !important;
    }
    .stTextArea textarea:focus {
        border-color: #6366f1 !important;
        box-shadow: 0 0 0 3px rgba(99,102,241,0.15) !important;
    }

    /* ── Primary Button ───────────────────────────── */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
        color: white !important;
        border: none !important;
        border-radius: 14px !important;
        padding: 0.75rem 2rem !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
        letter-spacing: 0.3px;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 14px rgba(99,102,241,0.35) !important;
    }
    .stButton > button[kind="primary"]:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(99,102,241,0.5) !important;
    }

    /* ── Example Buttons ──────────────────────────── */
    .stButton > button[kind="secondary"] {
        border-radius: 24px !important;
        border: 1.5px solid rgba(128,128,128,0.3) !important;
        background: var(--secondary-background-color, #ffffff) !important;
        font-size: 0.82rem !important;
        font-weight: 500 !important;
        color: var(--text-color, #475569) !important;
        padding: 0.45rem 1rem !important;
        transition: all 0.25s ease !important;
    }
    .stButton > button[kind="secondary"]:hover {
        border-color: #6366f1 !important;
        color: #6366f1 !important;
        background: rgba(99,102,241,0.1) !important;
        transform: translateY(-1px) !important;
    }

    /* ── Verdict Cards ────────────────────────────── */
    .verdict-card {
        border-radius: 16px;
        padding: 24px 28px;
        margin: 1rem 0;
        position: relative;
        overflow: hidden;
        color: #1e293b;
    }
    .verdict-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0;
        width: 6px;
        height: 100%;
    }
    .verdict-true {
        background: linear-gradient(135deg, #ecfdf5, #d1fae5);
        border: 1px solid #a7f3d0;
    }
    .verdict-true::before { background: linear-gradient(180deg, #10b981, #059669); }

    .verdict-false {
        background: linear-gradient(135deg, #fef2f2, #fee2e2);
        border: 1px solid #fecaca;
    }
    .verdict-false::before { background: linear-gradient(180deg, #ef4444, #dc2626); }

    .verdict-partial {
        background: linear-gradient(135deg, #fffbeb, #fef3c7);
        border: 1px solid #fde68a;
    }
    .verdict-partial::before { background: linear-gradient(180deg, #f59e0b, #d97706); }

    .verdict-nee {
        background: linear-gradient(135deg, #f8fafc, #f1f5f9);
        border: 1px solid #e2e8f0;
    }
    .verdict-nee::before { background: linear-gradient(180deg, #94a3b8, #64748b); }

    .verdict-misleading {
        background: linear-gradient(135deg, #fff7ed, #ffedd5);
        border: 1px solid #fed7aa;
    }
    .verdict-misleading::before { background: linear-gradient(180deg, #f97316, #ea580c); }

    .verdict-label {
        font-size: 1.6rem;
        font-weight: 800;
        margin: 0 0 6px 0;
        letter-spacing: -0.3px;
    }
    .verdict-conf {
        font-size: 0.9rem;
        font-weight: 500;
        margin: 0;
        opacity: 0.8;
    }
    .conf-bar-track {
        width: 180px;
        height: 7px;
        background: rgba(0,0,0,0.1);
        border-radius: 4px;
        margin-top: 6px;
        overflow: hidden;
    }
    .conf-bar-fill {
        height: 100%;
        border-radius: 4px;
        transition: width 0.8s ease;
    }

    /* ── Claim Info ────────────────────────────────── */
    .claim-info {
        background: var(--secondary-background-color, #f8fafc);
        border: 1px solid rgba(128,128,128,0.3);
        border-radius: 12px;
        padding: 16px 20px;
        margin: 12px 0 20px;
    }
    .claim-type-badge {
        display: inline-block;
        padding: 3px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 8px;
    }
    .badge-factual { background: #dbeafe; color: #1d4ed8; }
    .badge-opinion { background: #fef3c7; color: #92400e; }
    .badge-mixed { background: #ffedd5; color: #9a3412; }
    .badge-ambiguous { background: #f1f5f9; color: #475569; }

    .claim-text {
        font-size: 1.05rem;
        font-style: italic;
        color: var(--text-color, #334155);
        margin: 4px 0 0;
        line-height: 1.5;
    }
    .claim-label {
        font-size: 0.78rem;
        font-weight: 600;
        color: rgba(148,163,184,0.8);
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin: 0 0 2px;
    }

    /* ── Section Headers ──────────────────────────── */
    .section-header {
        font-size: 1.15rem;
        font-weight: 700;
        color: var(--text-color, #1e293b);
        margin: 1.5rem 0 0.75rem;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .section-header .icon {
        font-size: 1.2rem;
    }

    /* ── Reasoning Box ────────────────────────────── */
    .reasoning-box {
        background: var(--secondary-background-color, #ffffff);
        border: 1px solid rgba(128,128,128,0.3);
        border-radius: 14px;
        padding: 20px 24px;
        font-size: 0.95rem;
        line-height: 1.7;
        color: var(--text-color, #334155);
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }

    /* ── Evidence Cards ───────────────────────────── */
    .evidence-container {
        display: flex;
        flex-direction: column;
        gap: 10px;
    }

    /* ── Agent Trace ──────────────────────────────── */
    .step-log {
        font-family: 'SF Mono', 'Fira Code', monospace;
        font-size: 0.82rem;
        color: var(--text-color, #64748b);
        opacity: 0.75;
        padding: 3px 0;
        margin: 0;
        line-height: 1.6;
    }

    /* ── Success Bar ──────────────────────────────── */
    .stSuccess {
        border-radius: 12px !important;
    }

    /* ── Sidebar ──────────────────────────────────── */
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown h3 {
        font-size: 1rem;
        font-weight: 700;
        color: var(--text-color, #1e293b);
    }

    /* ── Pipeline Steps (Sidebar) ─────────────────── */
    .pipeline-step {
        display: flex;
        align-items: flex-start;
        gap: 12px;
        padding: 10px 0;
        border-bottom: 1px solid #e2e8f0;
    }
    .pipeline-step:last-child { border-bottom: none; }
    .step-num {
        width: 28px;
        height: 28px;
        border-radius: 50%;
        background: linear-gradient(135deg, #6366f1, #8b5cf6);
        color: white;
        font-size: 0.75rem;
        font-weight: 700;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    }
    .step-content {
        flex: 1;
    }
    .step-title {
        font-weight: 600;
        font-size: 0.85rem;
        color: var(--text-color, #1e293b);
        margin: 0;
    }
    .step-desc {
        font-size: 0.78rem;
        color: var(--text-color, #64748b);
        opacity: 0.7;
        margin: 2px 0 0;
    }

    /* ── Tech Pill Badges ─────────────────────────── */
    .tech-pills {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-top: 8px;
    }
    .tech-pill {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.72rem;
        font-weight: 600;
        background: rgba(99,102,241,0.15);
        color: #818cf8;
        border: 1px solid rgba(99,102,241,0.3);
    }

    /* ── KB Metric Card ───────────────────────────── */
    .kb-metric {
        background: linear-gradient(135deg, #6366f1, #8b5cf6);
        border-radius: 14px;
        padding: 20px;
        text-align: center;
        color: white;
        margin: 12px 0;
    }
    .kb-metric .num {
        font-size: 2.2rem;
        font-weight: 800;
        margin: 0;
        line-height: 1;
    }
    .kb-metric .label {
        font-size: 0.8rem;
        opacity: 0.85;
        margin: 4px 0 0;
        font-weight: 500;
    }

    /* ── Footer ───────────────────────────────────── */
    .footer {
        text-align: center;
        padding: 2rem 0 1rem;
        color: var(--text-color, #94a3b8);
        opacity: 0.6;
        font-size: 0.8rem;
    }
    .footer-pills {
        display: flex;
        justify-content: center;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 8px;
    }
    .footer-pill {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 0.7rem;
        background: var(--secondary-background-color, #f1f5f9);
        color: var(--text-color, #64748b);
        border: 1px solid rgba(128,128,128,0.2);
    }

    /* ── Expander Styling ─────────────────────────── */
    .streamlit-expanderHeader {
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        border-radius: 12px !important;
    }
    details {
        border-radius: 12px !important;
        border: 1px solid rgba(128,128,128,0.3) !important;
    }

    /* ── Examples Label ───────────────────────────── */
    .examples-label {
        font-size: 0.85rem;
        font-weight: 600;
        color: var(--text-color, #94a3b8);
        opacity: 0.6;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin: 0.5rem 0 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# ── Seed KB on first run ─────────────────────────────────────────────
@st.cache_resource
def init_system():
    seed()
    return ClaimVerifier()

verifier = init_system()

# ── Sidebar ───────────────────────────────────────────────────────────
with st.sidebar:
    vs = VectorStore()

    # KB Metric
    st.markdown(f"""
    <div class="kb-metric">
        <p class="num">{vs.count()}</p>
        <p class="label">Evidence in Knowledge Base</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### How It Works")

    pipeline_steps = [
        ("Classify & Extract", "LLM classifies claim type and extracts verifiable facts"),
        ("KB Retrieval", "Semantic search over ChromaDB vector store"),
        ("Cross-Encoder Rerank", "Precision reranking with ms-marco-MiniLM"),
        ("Sufficiency Check", "Agent decides if KB evidence is enough"),
        ("Web Search", "Trusted news & fact-checkers via DuckDuckGo"),
        ("Index & Grow", "New web evidence stored back into KB"),
        ("LLM Verdict", "GPT-4o-mini generates verdict with citations"),
    ]

    steps_html = ""
    for i, (title, desc) in enumerate(pipeline_steps, 1):
        steps_html += f"""
        <div class="pipeline-step">
            <div class="step-num">{i}</div>
            <div class="step-content">
                <p class="step-title">{title}</p>
                <p class="step-desc">{desc}</p>
            </div>
        </div>
        """
    st.markdown(steps_html, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### Tech Stack")
    st.markdown("""
    <div class="tech-pills">
        <span class="tech-pill">ChromaDB</span>
        <span class="tech-pill">all-MiniLM-L6-v2</span>
        <span class="tech-pill">ms-marco-MiniLM</span>
        <span class="tech-pill">GPT-4o-mini</span>
        <span class="tech-pill">DuckDuckGo</span>
        <span class="tech-pill">Streamlit</span>
    </div>
    """, unsafe_allow_html=True)


# ── Hero Header ──────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
    <div class="hero-icon">🔍</div>
    <h1>Real-Time News Claim Verifier</h1>
    <p>Agentic RAG pipeline — retrieves, reranks, cross-checks, and explains</p>
</div>
""", unsafe_allow_html=True)

# ── Main input ────────────────────────────────────────────────────────
col1, col2 = st.columns([5, 1])
with col1:
    claim_input = st.text_area(
        "Enter a claim to verify",
        placeholder="e.g., 'The Earth is flat' or 'India's GDP grew 8% in 2025' or paste a headline...",
        height=100,
        label_visibility="collapsed",
    )
with col2:
    st.markdown("<div style='height: 28px'></div>", unsafe_allow_html=True)
    verify_btn = st.button("Verify Claim", type="primary", use_container_width=True)

# ── Example claims ────────────────────────────────────────────────────
st.markdown('<p class="examples-label">Try an example</p>', unsafe_allow_html=True)
examples = [
    "The Earth is flat",
    "COVID-19 vaccines cause autism",
    "Humans first landed on the Moon in 1969",
    "5G towers spread coronavirus",
    "Climate change is a hoax",
]
example_cols = st.columns(len(examples))
for i, ex in enumerate(examples):
    with example_cols[i]:
        if st.button(ex, key=f"ex_{i}", use_container_width=True):
            claim_input = ex
            verify_btn = True


# ── Verdict rendering helpers ────────────────────────────────────────
def get_verdict_class(verdict: str) -> str:
    v = verdict.lower()
    if v == "true":
        return "verdict-true"
    elif v == "false":
        return "verdict-false"
    elif "partial" in v:
        return "verdict-partial"
    elif "misleading" in v or "not verifiable" in v:
        return "verdict-misleading"
    return "verdict-nee"


def get_verdict_emoji(verdict: str) -> str:
    v = verdict.lower()
    if v == "true":
        return "✅"
    elif v == "false":
        return "❌"
    elif "partial" in v:
        return "⚠️"
    elif "misleading" in v:
        return "🟠"
    elif "not verifiable" in v:
        return "💬"
    return "❓"


def get_verdict_color(verdict: str) -> str:
    v = verdict.lower()
    if v == "true":
        return "#059669"
    elif v == "false":
        return "#dc2626"
    elif "partial" in v:
        return "#d97706"
    elif "misleading" in v or "not verifiable" in v:
        return "#ea580c"
    return "#64748b"


def render_result(result: VerificationResult):
    """Render the verification result with modern styling."""
    emoji = get_verdict_emoji(result.verdict)
    css_class = get_verdict_class(result.verdict)
    color = get_verdict_color(result.verdict)
    conf_pct = int(result.confidence * 100)

    # ── Verdict Banner ──
    st.markdown(f"""
    <div class="verdict-card {css_class}">
        <p class="verdict-label">{emoji} {result.verdict}</p>
        <p class="verdict-conf">Confidence: <strong>{conf_pct}%</strong></p>
        <div class="conf-bar-track">
            <div class="conf-bar-fill" style="width:{conf_pct}%; background:{color};"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Claim Info Card ──
    badge_class = {
        "FACTUAL": "badge-factual",
        "OPINION": "badge-opinion",
        "MIXED": "badge-mixed",
        "AMBIGUOUS": "badge-ambiguous",
    }.get(result.claim_type, "badge-ambiguous")

    badge_icon = {
        "FACTUAL": "🔬",
        "OPINION": "💬",
        "MIXED": "🔀",
        "AMBIGUOUS": "❔",
    }.get(result.claim_type, "❔")

    claim_info_html = f'<div class="claim-info">'
    if result.claim_type:
        claim_info_html += f'<span class="claim-type-badge {badge_class}">{badge_icon} {result.claim_type}</span>'

    if result.original_claim and result.original_claim != result.claim:
        claim_info_html += f"""
            <p class="claim-label">Original Input</p>
            <p class="claim-text">"{result.original_claim}"</p>
            <p class="claim-label" style="margin-top:10px;">Extracted Claim</p>
            <p class="claim-text" style="color:#6366f1; font-weight:500;">"{result.claim}"</p>
        """
    else:
        claim_info_html += f"""
            <p class="claim-label">Verified Claim</p>
            <p class="claim-text">"{result.claim}"</p>
        """
    claim_info_html += '</div>'
    st.markdown(claim_info_html, unsafe_allow_html=True)

    # ── Reasoning ──
    st.markdown('<div class="section-header"><span class="icon">💡</span> Reasoning</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="reasoning-box">{result.reasoning}</div>', unsafe_allow_html=True)

    # ── Evidence ──
    if result.evidence:
        st.markdown(f'<div class="section-header"><span class="icon">📄</span> Evidence ({len(result.evidence)} sources)</div>', unsafe_allow_html=True)

        for i, ev in enumerate(result.evidence, 1):
            origin_badge = {
                "kb": "🗄 Knowledge Base",
                "web": "🌐 Web Source",
                "fact_check": "✅ Fact-Checker",
            }.get(ev.origin, "📄 Source")

            stars = ""
            if ev.score >= 5.0:
                stars = " ⭐⭐⭐"
            elif ev.score >= 3.0:
                stars = " ⭐⭐"
            elif ev.score >= 1.0:
                stars = " ⭐"

            with st.expander(f"[{i}] {origin_badge}  —  relevance {ev.score:.2f}{stars}"):
                st.markdown(ev.text)
                if ev.source:
                    st.markdown(f"🔗 [{ev.source}]({ev.source})")

    # ── Agent Trace ──
    if result.steps:
        st.markdown('<div class="section-header"><span class="icon">🤖</span> Agent Trace</div>', unsafe_allow_html=True)
        with st.expander("View step-by-step agent decisions"):
            for step in result.steps:
                st.markdown(f'<p class="step-log">{step}</p>', unsafe_allow_html=True)


# ── Verification ──────────────────────────────────────────────────────
if verify_btn and claim_input and claim_input.strip():
    with st.spinner("Verifying claim — retrieving, reranking, cross-checking..."):
        start = time.time()
        result = verifier.verify(claim_input.strip())
        elapsed = time.time() - start

    st.success(f"Verification complete in {elapsed:.1f}s")
    render_result(result)

    # Update KB count in sidebar
    new_count = VectorStore().count()
    st.sidebar.markdown(f"""
    <div class="kb-metric">
        <p class="num">{new_count}</p>
        <p class="label">Evidence in Knowledge Base</p>
    </div>
    """, unsafe_allow_html=True)

elif verify_btn:
    st.warning("Please enter a claim to verify.")

# ── Footer ────────────────────────────────────────────────────────────
st.markdown("""
<div class="footer">
    <p>Built with Agentic RAG</p>
    <div class="footer-pills">
        <span class="footer-pill">ChromaDB</span>
        <span class="footer-pill">all-MiniLM-L6-v2</span>
        <span class="footer-pill">ms-marco-MiniLM</span>
        <span class="footer-pill">GPT-4o-mini</span>
        <span class="footer-pill">DuckDuckGo</span>
        <span class="footer-pill">Streamlit</span>
    </div>
</div>
""", unsafe_allow_html=True)
