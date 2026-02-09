# 🔍 Real-Time News Claim Verification — Agentic RAG

A production-ready claim verification system built with an **Agentic RAG** pipeline. Enter any claim, headline, or snippet — the system retrieves evidence, reranks it, cross-checks via web search, and delivers a transparent verdict with citations.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER INPUT                               │
│              (claim / headline / text snippet)                   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │  1. CLAIM NORMALISER   │  GPT-4o-mini extracts a
              │     (LLM Agent)        │  clean verifiable claim
              └────────────┬───────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │  2. KB RETRIEVAL       │  Semantic search over
              │     (ChromaDB + HNSW)  │  ChromaDB with cosine
              │     top-20 candidates  │  similarity + access_count
              └────────────┬───────────┘  boost
                           │
                           ▼
              ┌────────────────────────┐
              │  3. CROSS-ENCODER      │  ms-marco-MiniLM-L-6-v2
              │     RERANKING          │  reranks to top-5
              └────────────┬───────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │  4. SUFFICIENCY CHECK  │  LLM decides: is KB
              │     (Agent Decision)   │  evidence enough?
              └──────┬─────────┬───────┘
                     │         │
                YES  │         │  NO
                     │         ▼
                     │  ┌──────────────────────┐
                     │  │ 5a. TRUSTED NEWS     │  DuckDuckGo search
                     │  │     SEARCH           │  (reuters, bbc, ap…)
                     │  └──────────┬───────────┘
                     │             │
                     │             ▼
                     │  ┌──────────────────────┐
                     │  │ 5b. FACT-CHECKER     │  snopes, factcheck.org
                     │  │     SEARCH           │  politifact
                     │  └──────────┬───────────┘
                     │             │
                     │             ▼
                     │  ┌──────────────────────┐
                     │  │ 5c. INDEX NEW        │  Web results stored
                     │  │     EVIDENCE → KB    │  back into ChromaDB
                     │  └──────────┬───────────┘  (ever-growing KB)
                     │             │
                     ▼             ▼
              ┌────────────────────────┐
              │  6. FINAL RERANK       │  All evidence reranked
              │     (Cross-Encoder)    │  together
              └────────────┬───────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │  7. LLM VERDICT        │  GPT-4o-mini generates
              │     + CITATIONS        │  verdict, reasoning,
              │     + REASONING        │  and [N] citations
              └────────────┬───────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │  STREAMLIT UI          │  Colour-coded verdict,
              │  (Result Display)      │  evidence cards, agent
              │                        │  trace log
              └────────────────────────┘
```

## 📦 Tech Stack

| Component         | Technology                          |
|--------------------|-------------------------------------|
| **Embedding**      | `all-MiniLM-L6-v2` (384-dim)       |
| **Vector DB**      | ChromaDB (persistent, HNSW index)   |
| **Reranker**       | `ms-marco-MiniLM-L-6-v2` (cross-encoder) |
| **LLM**            | GPT-4o-mini (OpenAI)               |
| **Web Search**     | DuckDuckGo (no API key needed)      |
| **UI**             | Streamlit + Chrome Extension        |
| **API**            | Flask + Flask-CORS                  |

## 🚀 Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set your OpenAI API key
```bash
# Windows
set OPENAI_API_KEY=sk-your-key-here

# Linux/Mac
export OPENAI_API_KEY=sk-your-key-here
```

### 3. Run the Streamlit app
```bash
streamlit run app.py
```

The app will:
- Auto-seed the knowledge base with verified facts on first run
- Open in your browser at `http://localhost:8501`

### 4. Run the Flask API (for Chrome Extension)
```bash
python api.py
```
The API runs on `http://localhost:5000`.

### 5. Install the Chrome Extension (Bonus)
1. Open Chrome → `chrome://extensions/`
2. Enable **Developer mode** (top-right toggle)
3. Click **Load unpacked** → select the `chrome_extension/` folder
4. Make sure the Flask API is running (`python api.py`)
5. Browse any website → **highlight text** → click the floating **🔍 Verify Claim** button
6. Or right-click selected text → **"Verify Claim"** from context menu
7. Or click the extension icon in the toolbar to type a claim manually

> **Note:** On first run, `python generate_icons.py` creates PNG icons for the extension (optional — it works without them).

## 🧠 Technical Details

### Chunking Strategy
- Documents are stored as atomic evidence snippets (1-3 sentences each)
- Web search results are indexed as-is (snippet-level granularity)
- No large-document chunking needed — evidence is already snippet-sized

### Embedding Model
- **`all-MiniLM-L6-v2`** — 384-dimensional dense vectors
- Fast inference (~14k sentences/sec on GPU), good semantic quality
- Cosine similarity for retrieval

### Reranking Approach
- **Stage 1**: Retrieve top-20 candidates via cosine similarity (fast ANN search)
- **Stage 2**: Cross-encoder `ms-marco-MiniLM-L-6-v2` reranks to top-5
- Cross-encoder scores both claim and evidence jointly → much higher precision
- Minimum relevance threshold filters low-quality matches

### Knowledge Base Design
- **Static KB**: Pre-seeded with verified facts (science, history, health)
- **Dynamic KB**: Web search results are automatically indexed back
- **Ever-growing**: Each verification enriches the KB for future queries
- **Access-count boosting**: Frequently retrieved docs get score boosts

### Live Web Validation Strategy
1. **Trusted news search**: Reuters, BBC, AP News, NYT, etc.
2. **Fact-checker search**: Snopes, FactCheck.org, PolitiFact
3. **Broad fallback**: General web search if evidence is still thin
4. All results indexed into KB for future retrieval

### Verification / Validation Logic (Agentic)
1. LLM normalises the raw input into a clean, verifiable claim
2. Agent retrieves from KB and checks sufficiency
3. If insufficient → multi-step web search (trusted → fact-checkers → broad)
4. All evidence is deduplicated and reranked
5. LLM generates structured verdict with mandatory citations
6. If no evidence found → outputs **"Not Enough Evidence"** (never fabricates)

### Verdicts
- ✅ **True** — Claim is supported by evidence
- ❌ **False** — Claim is contradicted by evidence
- ⚠️ **Partially True** — Some aspects are correct, others are not
- 🟠 **Misleading** — Technically true but presented in a deceptive way
- ❓ **Not Enough Evidence** — Cannot verify with available evidence

## 🌐 Chrome Extension (Bonus)

The Chrome Extension provides the preferred **highlight → verify → popup** workflow:

```
┌──────────────────────────────────────────────────────────┐
│  BROWSER (any webpage)                                   │
│                                                          │
│  1. User highlights text                                 │
│  2. Floating "🔍 Verify Claim" button appears            │
│  3. Click → overlay shows loading spinner                │
│                     │                                    │
│                     ▼                                    │
│  ┌──────────────────────────────┐                        │
│  │  Chrome Extension            │                        │
│  │  (content.js + background.js)│                        │
│  └──────────────┬───────────────┘                        │
│                 │ POST /api/verify                        │
│                 ▼                                         │
│  ┌──────────────────────────────┐                        │
│  │  Flask API (localhost:5000)  │                        │
│  │  → ClaimVerifier.verify()    │                        │
│  │  → Full Agentic RAG pipeline │                        │
│  └──────────────┬───────────────┘                        │
│                 │                                         │
│                 ▼                                         │
│  4. Result popup with verdict, reasoning, citations      │
└──────────────────────────────────────────────────────────┘
```

**Three ways to verify:**
- **Floating button** — highlight text on any page, click the blue button
- **Right-click menu** — select text → right-click → "Verify Claim"
- **Popup** — click extension icon → type claim manually

## 📁 Project Structure

```
H1/
├── app.py                  # Streamlit web app UI
├── api.py                  # Flask API backend (for Chrome Extension)
├── agent.py                # Agentic RAG verification pipeline
├── vector_store.py         # ChromaDB vector store wrapper
├── reranker.py             # Cross-encoder reranker
├── web_search.py           # DuckDuckGo web search module
├── seed_kb.py              # Static knowledge base seeder
├── config.py               # Configuration constants
├── generate_icons.py       # PNG icon generator for extension
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
├── README.md               # This file
└── chrome_extension/       # Chrome Extension (Bonus)
    ├── manifest.json        # Extension manifest (MV3)
    ├── background.js        # Service worker (context menu, API calls)
    ├── content.js           # Content script (floating button, overlay)
    ├── content.css          # Content script styles
    ├── popup.html           # Extension popup UI
    ├── popup.js             # Popup logic
    └── icons/               # Extension icons (run generate_icons.py)
```

## ⚠️ Constraints Followed
- ✅ Always cites sources with URLs
- ✅ Never fabricates sources (LLM is constrained by retrieved evidence)
- ✅ Outputs "Not Enough Evidence" when evidence is missing
- ✅ Transparent reasoning with step-by-step agent trace

## 🏆 Bonus Features
- ✅ **Chrome Extension** with highlight → verify → popup workflow
- ✅ **Right-click context menu** verification
- ✅ **Cross-encoder reranking** for precision retrieval
- ✅ **Ever-growing knowledge base** — web results indexed back into ChromaDB
- ✅ **Access-count boosting** — popular evidence ranks higher over time
- ✅ **Multi-step agentic workflow** — agent decides when to search web vs use KB
- ✅ **Fact-checker integration** — searches Snopes, FactCheck.org, PolitiFact
- ✅ **Deduplication** — removes near-duplicate evidence before verdict
