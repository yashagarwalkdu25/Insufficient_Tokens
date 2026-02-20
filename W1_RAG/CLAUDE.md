# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Real-Time News Claim Verification System using Agentic RAG (Retrieval-Augmented Generation). This system verifies claims by retrieving evidence from a vector knowledge base, cross-checking with web sources, and generating verdicts with citations using GPT-4o-mini.

**Tech Stack**: Python 3.9, ChromaDB (vector store), sentence-transformers (embeddings), OpenAI GPT-4o-mini, DuckDuckGo search, Streamlit (UI), Flask (API)

## Setup and Running

### Environment Setup
```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# Set OpenAI API key (required)
export OPENAI_API_KEY=sk-your-key-here  # Mac/Linux
set OPENAI_API_KEY=sk-your-key-here     # Windows
```

### Running the Application
```bash
# Streamlit web UI (main interface) — auto-seeds KB on first run
streamlit run app.py
# Opens at http://localhost:8501

# Flask API (for Chrome Extension)
python api.py
# Runs on http://localhost:5000

# Manually seed knowledge base (optional)
python seed_kb.py

# Generate Chrome Extension icons (optional)
python generate_icons.py
```

### Chrome Extension Installation
1. Open `chrome://extensions/`
2. Enable "Developer mode"
3. Click "Load unpacked" → select `chrome_extension/` folder
4. Ensure Flask API is running (`python api.py`)

## Architecture

### Core Pipeline (agent.py)
The `ClaimVerifier` class implements an enhanced 7-step Agentic RAG pipeline:

1. **Claim Classification & Extraction**: LLM classifies claim type (FACTUAL/OPINION/MIXED/AMBIGUOUS) and extracts verifiable components
   - Rejects subjective opinions upfront
   - Decomposes mixed claims into factual parts
   - Provides clear feedback for ambiguous claims
2. **KB Retrieval**: Semantic search over ChromaDB with enhanced metadata (top-20 candidates)
3. **Multi-Stage Reranking**:
   - Cross-encoder relevance scoring
   - Source credibility weighting (+0.3 to +0.5 boost for trusted sources)
   - Source diversity enforcement (max 2 results per domain)
   - Final top-5 selection
4. **Sufficiency Check**: LLM decides if KB evidence is sufficient
5. **Multi-Stage Web Search** (if needed):
   - Trusted news sources (Reuters, BBC, AP, etc.)
   - Fact-checker sites (Snopes, FactCheck.org, PolitiFact)
   - Broad web search (fallback)
6. **Index New Evidence**: Web results automatically added to KB with full metadata (ever-growing)
7. **LLM Verdict**: Generates verdict with mandatory citations

**Key Improvements**:
- Context isolation with session IDs (no carryover between verifications)
- Claim type classification prevents wasted processing on opinions
- Multi-stage reranking with credibility scoring improves evidence quality
- Enhanced metadata schema for robust source tracking

### Vector Store (vector_store.py)
- **Embedding Model**: `all-MiniLM-L6-v2` (384-dimensional, fast inference)
- **Database**: ChromaDB with persistent storage in `./chroma_db/`
- **Index**: HNSW (Hierarchical Navigable Small World) with cosine similarity
- **Access-Count Boosting**: Frequently retrieved documents get score boosts (0.02 per access)
- **Chunking**: Evidence stored as atomic snippets (1-3 sentences), no large-document chunking

**Enhanced Metadata Schema**:
- `source_type`: news/academic/fact_checker/government/unknown
- `source_credibility`: 0-1 score based on domain (from SOURCE_CREDIBILITY in config.py)
- `verification_count`: Number of times used in verifications
- `avg_relevance`: Average rerank score across all uses
- `domain`: Extracted domain from source URL
- `text_length`: Character count of evidence
- `last_accessed`: ISO timestamp of last retrieval
- `language`: Content language (default: "en")

### Reranking (reranker.py)
- **Model**: `cross-encoder/ms-marco-MiniLM-L-6-v2`
- **Purpose**: High-precision reranking after fast semantic search
- **Threshold**: Filters results below `MIN_RELEVANCE_SCORE` (0.3)
- **Strategy**: Multi-stage retrieval

**Multi-Stage Reranking Pipeline**:
1. **Semantic Search**: Fast HNSW retrieval (top-20)
2. **Cross-Encoder**: Relevance scoring
3. **Credibility Boost**: Add credibility-based score adjustment
   - Formula: `final_score = relevance + (credibility - 0.5) * boost_factor`
   - Boost factor: 0.3 (configurable in config.py)
4. **Source Diversity**: Limit results per domain (max 2)
5. **Final Selection**: Return top-5

**Source Credibility Scores** (config.py):
- Fact-checkers (Snopes, FactCheck.org, PolitiFact): 0.95
- Government/Scientific (WHO, CDC, NASA): 0.95
- News agencies (Reuters, AP, BBC): 0.85-0.90
- Major newspapers (NYT, WashPost, Guardian): 0.80
- Academic sources (Nature, Science, ArXiv): 0.80-0.90
- Unknown domains: 0.5 (neutral)

### Web Search (web_search.py)
Three specialized search functions:
- `search_web()`: General DuckDuckGo search
- `search_trusted()`: Filters to trusted news domains (see `config.TRUSTED_DOMAINS`)
- `search_fact_checkers()`: Targets fact-checking sites

**Note**: Uses DuckDuckGo (no API key required), results are automatically indexed into KB.

### Configuration (config.py)
All constants centralized:
- LLM settings (model, temperature)
- Embedding/reranker models
- Retrieval parameters (top-k values, relevance thresholds)
- Trusted domains list
- ChromaDB paths

## File Organization

### Core Components
- **agent.py**: Agentic RAG verification pipeline (`ClaimVerifier` class)
- **vector_store.py**: ChromaDB wrapper (`VectorStore` class)
- **reranker.py**: Cross-encoder reranking (`Reranker` class)
- **web_search.py**: DuckDuckGo search functions

### Interfaces
- **app.py**: Streamlit web UI with example claims and agent trace viewer
- **api.py**: Flask REST API with `/api/verify` and `/api/health` endpoints

### Supporting
- **seed_kb.py**: Seeds initial knowledge base with 10 verified facts (NASA, WHO, CDC sources)
- **config.py**: Central configuration and environment variables
- **generate_icons.py**: Creates PNG icons for Chrome Extension

### Chrome Extension (chrome_extension/)
- **manifest.json**: Manifest V3 configuration
- **background.js**: Service worker (context menu, API calls)
- **content.js**: Floating verification button, overlay UI
- **popup.js/html**: Extension toolbar popup
- **content.css**: Content script styles

## Key Concepts

### Ever-Growing Knowledge Base
Web search results are automatically indexed back into ChromaDB, so the knowledge base continuously expands with each verification. Popular evidence naturally ranks higher over time via access-count boosting.

### Evidence Origins
Evidence is tagged with origin: `"kb"` (knowledge base), `"web"` (trusted news), or `"fact_check"` (fact-checker sites). This is visible in the UI and helps users assess source credibility.

### Claim Types (New Feature)
The system now classifies claims before verification:
- **FACTUAL**: Objective, verifiable statements (e.g., "The Earth is flat")
- **OPINION**: Subjective preferences or value judgments (e.g., "Minecraft is the best game") — **Rejected upfront** with explanation
- **MIXED**: Contains both factual and subjective elements (e.g., "Minecraft is the best 2D game") — System extracts factual part ("Minecraft is a 2D game")
- **AMBIGUOUS**: Too vague or unclear to verify (e.g., "It's true") — Returns clarification request

This prevents wasted processing on non-verifiable claims and provides clearer user feedback.

### Verdict Types
System returns one of six verdicts:
- **True**: Supported by evidence
- **False**: Contradicted by evidence
- **Partially True**: Mixed support/contradiction
- **Misleading**: Technically true but deceptive presentation
- **Not Enough Evidence**: Insufficient evidence (never fabricates)
- **Not Verifiable** (NEW): Claim is subjective opinion or too ambiguous

### Citations
The LLM is constrained to cite evidence using `[1]`, `[2]`, etc. matching the provided evidence list. Never fabricates sources.

### Context Isolation (New Feature)
Each verification gets a unique `session_id` (UUID) to prevent context carryover:
- No conversation history between verifications
- Fresh LLM calls for each claim (stateless)
- Session IDs logged in verification results
- Prevents previous claims from affecting new ones

This fixes the issue where multiple claims in sequence would influence each other.

## Development Guidelines

### Adding New Seed Facts
Edit `SEED_FACTS` list in `seed_kb.py`. Each fact needs:
- `text`: The factual statement
- `source`: Authoritative URL
- `details`: Human-readable source description

Delete `./chroma_db/` folder and restart to re-seed.

### Adjusting Retrieval Parameters
Modify in `config.py`:
- `TOP_K_RETRIEVAL`: Number of candidates for initial semantic search (default: 20)
- `TOP_K_RERANK`: Number to keep after cross-encoder reranking (default: 5)
- `MIN_RELEVANCE_SCORE`: Minimum cross-encoder score to keep evidence (default: 0.3)

### Adding Trusted Domains
Edit `TRUSTED_DOMAINS` list in `config.py`. Used by `search_trusted()` to filter web results.

### Modifying LLM Behavior
- **Model**: Change `LLM_MODEL` in `config.py` (default: `gpt-4o-mini`)
- **Temperature**: Adjust `LLM_TEMPERATURE` for more/less creative responses (default: 0.1)
- **Prompts**: Edit system prompts in `agent.py`:
  - `_normalise_claim()`: Claim extraction prompt
  - `_has_enough_evidence()`: Sufficiency check prompt
  - `_generate_verdict()`: Final verdict generation prompt

### Debugging Agent Decisions
The `VerificationResult.steps` list contains the agent trace (visible in Streamlit UI under "Agent Trace" expander). Useful for understanding why the agent chose to search the web or how it interpreted evidence.

## Recent Improvements (v2.0)

### Critical Fixes
1. **Claim Type Classification**: System now detects and handles FACTUAL, OPINION, MIXED, and AMBIGUOUS claims properly
   - Rejects subjective opinions with clear explanation
   - Extracts factual components from mixed claims
   - Example: "Minecraft is the best 2D game" → extracts "Minecraft is a 2D game"

2. **Context Isolation**: Each verification gets unique session ID to prevent context carryover between claims

3. **Multi-Stage Reranking**: Enhanced reranking with source credibility scoring
   - Trusted sources get +0.3 to +0.5 boost
   - Source diversity enforcement (max 2 per domain)
   - Better evidence quality overall

4. **Enhanced Metadata**: Robust metadata schema with 12+ fields per evidence
   - Source type classification
   - Credibility scores
   - Usage tracking
   - Temporal information

### UI Improvements
- Claim type badges (🔵 FACTUAL, 🟡 OPINION, 🟠 MIXED, ⚪ AMBIGUOUS)
- Source credibility stars (⭐⭐⭐ for high credibility)
- Original claim vs extracted claim display
- Better error messages for non-verifiable claims

## Important Notes

- **OpenAI API Key Required**: The system will fail without `OPENAI_API_KEY` environment variable
- **ChromaDB Persistence**: Data persists in `./chroma_db/` directory. Delete to reset the knowledge base
- **Metadata Migration**: Old evidence is compatible with new schema (new fields added gracefully)
- **First Run Seeding**: Both `app.py` and `api.py` auto-seed the KB if empty (calls `seed()`)
- **DuckDuckGo Rate Limits**: If web searches fail repeatedly, DuckDuckGo may be rate-limiting. Add delays between requests
- **Chrome Extension CORS**: The Flask API enables CORS for all origins (`CORS(app)`). Restrict in production
- **API Port**: Flask API must run on port 5000 for Chrome Extension to work (hardcoded in `background.js`)
