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
    .verdict-true { background: #d4edda; border-left: 5px solid #28a745; padding: 16px; border-radius: 8px; }
    .verdict-false { background: #f8d7da; border-left: 5px solid #dc3545; padding: 16px; border-radius: 8px; }
    .verdict-partial { background: #fff3cd; border-left: 5px solid #ffc107; padding: 16px; border-radius: 8px; }
    .verdict-nee { background: #e2e3e5; border-left: 5px solid #6c757d; padding: 16px; border-radius: 8px; }
    .verdict-misleading { background: #ffe0cc; border-left: 5px solid #fd7e14; padding: 16px; border-radius: 8px; }
    .evidence-card {
        background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 8px;
        padding: 12px; margin-bottom: 8px;
    }
    .step-log { font-family: monospace; font-size: 0.85em; color: #495057; }
    .confidence-bar { height: 8px; border-radius: 4px; margin-top: 4px; }
    .source-link { color: #0066cc; text-decoration: none; font-size: 0.85em; }
    .header-container { text-align: center; padding: 1rem 0; }
    .metric-box {
        background: #f0f2f6; border-radius: 8px; padding: 12px; text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# ── Seed KB on first run ─────────────────────────────────────────────
@st.cache_resource
def init_system():
    seed()
    return ClaimVerifier()

verifier = init_system()

# ── Header ────────────────────────────────────────────────────────────
st.markdown('<div class="header-container">', unsafe_allow_html=True)
st.title("🔍 Real-Time News Claim Verifier")
st.caption("Agentic RAG pipeline — retrieves, reranks, cross-checks, and explains")
st.markdown('</div>', unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────
with st.sidebar:
    st.header("ℹ️ How It Works")
    st.markdown("""
1. **Claim Extraction** — LLM normalises your input into a verifiable claim
2. **KB Retrieval** — Semantic search over the vector knowledge base (ChromaDB)
3. **Cross-Encoder Reranking** — Precision reranking with `ms-marco-MiniLM-L-6-v2`
4. **Sufficiency Check** — Agent decides if KB evidence is enough
5. **Web Search** — If needed, searches trusted news & fact-checkers (DuckDuckGo)
6. **Index & Grow** — New web evidence is stored back into the KB
7. **LLM Verdict** — GPT-4o-mini generates verdict with citations
    """)
    st.divider()
    vs = VectorStore()
    st.metric("📚 Knowledge Base Size", vs.count())
    st.divider()
    st.markdown("**Tech Stack**")
    st.markdown("""
- **Embedding**: `all-MiniLM-L6-v2`
- **Vector DB**: ChromaDB (persistent)
- **Reranker**: `ms-marco-MiniLM-L-6-v2`
- **LLM**: GPT-4o-mini
- **Web Search**: DuckDuckGo
    """)

# ── Main input ────────────────────────────────────────────────────────
col1, col2 = st.columns([4, 1])
with col1:
    claim_input = st.text_area(
        "Enter a claim to verify",
        placeholder="e.g., 'The Earth is flat' or 'India's GDP grew 8% in 2025' or paste a headline…",
        height=100,
    )
with col2:
    st.markdown("<br>", unsafe_allow_html=True)
    verify_btn = st.button("🔎 Verify Claim", type="primary", use_container_width=True)

# ── Example claims ────────────────────────────────────────────────────
st.markdown("**Try an example:**")
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

# ── Verification ──────────────────────────────────────────────────────
def get_verdict_class(verdict: str) -> str:
    v = verdict.lower()
    if v == "true":
        return "verdict-true"
    elif v == "false":
        return "verdict-false"
    elif "partial" in v:
        return "verdict-partial"
    elif "misleading" in v:
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
    return "❓"

def render_result(result: VerificationResult):
    """Render the verification result."""
    emoji = get_verdict_emoji(result.verdict)
    css_class = get_verdict_class(result.verdict)

    # Verdict banner
    st.markdown(f"""
    <div class="{css_class}">
        <h2 style="margin:0">{emoji} Verdict: {result.verdict}</h2>
        <p style="margin:4px 0 0 0; font-size:0.9em;">
            Confidence: <strong>{result.confidence:.0%}</strong>
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Normalised claim
    st.markdown(f"**Verified claim:** *\"{result.claim}\"*")

    # Reasoning
    st.subheader("💡 Reasoning")
    st.markdown(result.reasoning)

    # Evidence
    if result.evidence:
        st.subheader(f"📄 Evidence ({len(result.evidence)} sources)")
        for i, ev in enumerate(result.evidence, 1):
            origin_badge = {
                "kb": "🗄️ Knowledge Base",
                "web": "🌐 Web",
                "fact_check": "✅ Fact-Checker",
            }.get(ev.origin, "📄 Source")
            with st.expander(f"[{i}] {origin_badge} — relevance {ev.score:.2f}"):
                st.markdown(ev.text)
                if ev.source:
                    st.markdown(f"🔗 **Source:** [{ev.source}]({ev.source})")

    # Agent steps
    if result.steps:
        st.subheader("🤖 Agent Trace")
        with st.expander("View step-by-step agent decisions"):
            for step in result.steps:
                st.markdown(f'<p class="step-log">{step}</p>', unsafe_allow_html=True)


if verify_btn and claim_input and claim_input.strip():
    with st.spinner("🔄 Verifying claim — retrieving, reranking, cross-checking…"):
        start = time.time()
        result = verifier.verify(claim_input.strip())
        elapsed = time.time() - start

    st.success(f"Verification complete in {elapsed:.1f}s")
    render_result(result)

    # Update KB count in sidebar
    st.sidebar.metric("📚 Knowledge Base Size", VectorStore().count())

elif verify_btn:
    st.warning("Please enter a claim to verify.")

# ── Footer ────────────────────────────────────────────────────────────
st.divider()
st.caption(
    "Built with Agentic RAG — ChromaDB · all-MiniLM-L6-v2 · ms-marco-MiniLM-L-6-v2 · "
    "GPT-4o-mini · DuckDuckGo · Streamlit"
)
