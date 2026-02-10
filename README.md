# Real-Time News Claim Verification System — Agentic RAG

A production-ready claim verification system built on an **Agentic Retrieval-Augmented Generation (RAG)** pipeline. The system accepts any claim, headline, or text snippet as input, retrieves and reranks evidence from a persistent vector knowledge base, optionally cross-checks against live web sources, and generates a transparent verdict backed by citations.

---

## Table of Contents

1. [System Architecture](#1-system-architecture)
2. [Verification Pipeline — Step-by-Step](#2-verification-pipeline--step-by-step)
3. [Core Components — Detailed Technical Reference](#3-core-components--detailed-technical-reference)
   - 3.1 [Claim Verifier Agent (`agent.py`)](#31-claim-verifier-agent-agentpy)
   - 3.2 [Vector Store (`vector_store.py`)](#32-vector-store-vector_storepy)
   - 3.3 [Reranker (`reranker.py`)](#33-reranker-rerankerpy)
   - 3.4 [Web Search (`web_search.py`)](#34-web-search-web_searchpy)
   - 3.5 [Configuration (`config.py`)](#35-configuration-configpy)
4. [Metadata Schema — Design, Fields, and Usage](#4-metadata-schema--design-fields-and-usage)
5. [Knowledge Base Design — Ever-Growing Architecture](#5-knowledge-base-design--ever-growing-architecture)
6. [Source Credibility System](#6-source-credibility-system)
7. [Claim Classification System](#7-claim-classification-system)
8. [Verdict Types and Decision Logic](#8-verdict-types-and-decision-logic)
9. [User Interfaces](#9-user-interfaces)
   - 9.1 [Streamlit Web UI (`app.py`)](#91-streamlit-web-ui-apppy)
   - 9.2 [Flask REST API (`api.py`)](#92-flask-rest-api-apipy)
   - 9.3 [Chrome Extension (`chrome_extension/`)](#93-chrome-extension-chrome_extension)
10. [Setup and Installation](#10-setup-and-installation)
11. [Project Structure](#11-project-structure)
12. [Configuration Reference](#12-configuration-reference)
13. [Development Guide](#13-development-guide)

---

## 1. System Architecture

The system follows a multi-stage agentic pipeline where an LLM-powered agent orchestrates the verification process. The agent makes autonomous decisions at each stage — classifying the claim, retrieving evidence, judging sufficiency, triggering web searches when needed, and generating a final verdict.

```
                         USER INPUT
              (claim / headline / text snippet)
                            |
                            v
               +------------------------+
               | 1. CLAIM CLASSIFIER    |  GPT-4o-mini classifies the claim
               |    & EXTRACTOR         |  as FACTUAL / OPINION / MIXED /
               |    (LLM Agent)         |  AMBIGUOUS and extracts the
               +-----------|------------+  verifiable component
                            |
              OPINION?      |     AMBIGUOUS?
          +-- return -------+------- return "Not Enough Evidence" --+
          |  "Not Verifiable"       (ask user to clarify)           |
          |                 |                                       |
          |    FACTUAL or MIXED (extracted claim)                   |
          |                 |                                       |
          |                 v                                       |
          |    +------------------------+                           |
          |    | 2. KB RETRIEVAL        |  all-MiniLM-L6-v2 encodes |
          |    |    (ChromaDB + HNSW)   |  claim -> cosine search   |
          |    |    top-20 candidates   |  over ChromaDB with       |
          |    +-----------|------------+  access-count boosting    |
          |                 |                                       |
          |                 v                                       |
          |    +------------------------+                           |
          |    | 3. CROSS-ENCODER       |  ms-marco-MiniLM-L-6-v2  |
          |    |    RERANKING           |  reranks to top-5         |
          |    |    + threshold filter  |  filters score < 0.3      |
          |    +-----------|------------+                           |
          |                 |                                       |
          |                 v                                       |
          |    +------------------------+                           |
          |    | 4. SUFFICIENCY CHECK   |  Checks: >= 2 evidence?   |
          |    |    (Agent Decision)    |  avg score >= 1.0?        |
          |    +--------|--------|------+  LLM says "yes"?          |
          |        YES  |        | NO                               |
          |             |        v                                  |
          |             | +------------------------+                |
          |             | | 5a. TRUSTED NEWS       |  DuckDuckGo    |
          |             | |     SEARCH             |  filtered to   |
          |             | |                        |  reuters, bbc, |
          |             | +-----------|------------+  ap, nyt...    |
          |             |             |                              |
          |             |          2s delay (rate-limit protection)  |
          |             |             |                              |
          |             |             v                              |
          |             | +------------------------+                |
          |             | | 5b. FACT-CHECKER       |  snopes.com    |
          |             | |     SEARCH             |  factcheck.org |
          |             | |                        |  politifact.com|
          |             | +-----------|------------+                |
          |             |             |                              |
          |             |    Still < 2 relevant evidence?           |
          |             |         YES |                              |
          |             |          2s delay                         |
          |             |             |                              |
          |             |             v                              |
          |             | +------------------------+                |
          |             | | 5c. BROAD WEB SEARCH   |  Unrestricted  |
          |             | |     (fallback)         |  DuckDuckGo    |
          |             | +-----------|------------+                |
          |             |             |                              |
          |             |             v                              |
          |             | +------------------------+                |
          |             | | 5d. INDEX NEW EVIDENCE |  All web results|
          |             | |     INTO KB            |  stored back    |
          |             | +-----------|------------+  into ChromaDB  |
          |             |             |              (ever-growing KB)|
          |             v             v                              |
          |    +------------------------+                           |
          |    | 6. DEDUPLICATE         |  Remove near-duplicate    |
          |    |    + FINAL RERANK      |  evidence, then rerank    |
          |    |    (Cross-Encoder      |  ALL evidence together    |
          |    |     + Credibility)     |  with credibility scoring |
          |    +-----------|------------+                           |
          |                 |                                       |
          |                 v                                       |
          |    +------------------------+                           |
          |    | 7. LLM VERDICT         |  GPT-4o-mini generates    |
          |    |    + CITATIONS         |  structured JSON verdict  |
          |    |    + CONFIDENCE        |  with [N] citations and   |
          |    |    + REASONING         |  confidence score         |
          |    +-----------|------------+                           |
          |                 |                                       |
          +---------->     v  <---------+---------------------------+
               +------------------------+
               | RESULT OUTPUT          |  VerificationResult with:
               | (VerificationResult)   |  verdict, confidence,
               |                        |  reasoning, evidence[],
               |                        |  steps[], session_id,
               |                        |  claim_type
               +------------------------+
                            |
                            v
               +------------------------+
               | STREAMLIT UI / API /   |  Colour-coded verdict,
               | CHROME EXTENSION       |  evidence cards, agent
               |                        |  trace log, credibility
               +------------------------+  stars
```

### Tech Stack

| Component | Technology | Purpose |
|---|---|---|
| **Embedding Model** | `all-MiniLM-L6-v2` (384-dim) | Encodes claims and evidence into dense vectors for semantic search |
| **Vector Database** | ChromaDB (persistent, HNSW index) | Stores and retrieves evidence embeddings with cosine similarity |
| **Reranker** | `cross-encoder/ms-marco-MiniLM-L-6-v2` | High-precision re-scoring of candidate evidence pairs |
| **LLM** | GPT-4o-mini (OpenAI) | Claim classification, sufficiency checks, verdict generation |
| **Web Search** | DuckDuckGo (no API key) | Live evidence retrieval from trusted news and fact-checkers |
| **Web UI** | Streamlit | Interactive verification interface with agent trace viewer |
| **REST API** | Flask + Flask-CORS | Backend API powering the Chrome Extension |
| **Browser Extension** | Chrome Extension (Manifest V3) | Highlight-to-verify workflow on any webpage |

---

## 2. Verification Pipeline — Step-by-Step

This section walks through exactly what happens when a user submits a claim for verification.

### Step 1: Claim Classification and Extraction

**File**: `agent.py` — `_extract_and_classify_claim()`

When raw user input arrives, the system does NOT immediately search for evidence. Instead, it first classifies the claim into one of four types using GPT-4o-mini with `temperature=0` (deterministic output) and `response_format={"type": "json_object"}` (guaranteed valid JSON).

**Classification categories:**

| Type | Description | System Behaviour |
|---|---|---|
| `FACTUAL` | Objective, verifiable statement (even if false) | Proceeds with full verification pipeline |
| `OPINION` | Subjective preference or value judgment | Immediately returns "Not Verifiable" — no evidence retrieval |
| `MIXED` | Contains both factual and subjective parts | Extracts the factual component, discards subjective part, then verifies |
| `AMBIGUOUS` | Too vague or unclear to verify | Returns "Not Enough Evidence" with a clarification request |

**Examples of classification:**

| Input | Type | Extracted Claim |
|---|---|---|
| "The Earth is flat" | FACTUAL | "The Earth is flat" |
| "Minecraft is the best game" | OPINION | (rejected, not verified) |
| "Minecraft is the best 2D game" | MIXED | "Minecraft is a 2D game" |
| "It's true" | AMBIGUOUS | (rejected, ask user to clarify) |
| "Water boils at 50C" | FACTUAL | "Water boils at 50C" (error preserved) |

**Key design decision**: The system intentionally preserves factual errors in the extracted claim. If a user says "Water boils at 50C", the system does NOT correct it to 100C — it extracts "Water boils at 50C" as-is and verifies that claim against evidence, allowing the evidence to reveal the error.

**Fallback behaviour**: If the LLM classification call fails (network error, API timeout, etc.), the system falls back to treating the input as `FACTUAL` and passes the raw text through. This ensures the system degrades gracefully rather than blocking.

### Step 2: Knowledge Base Retrieval

**Files**: `agent.py` — `_retrieve_kb()`, `vector_store.py` — `query()`

The normalised claim is encoded into a 384-dimensional dense vector using `all-MiniLM-L6-v2` and searched against the ChromaDB collection using HNSW (Hierarchical Navigable Small World) approximate nearest-neighbor search with cosine similarity.

**Retrieval process:**

1. The claim text is encoded into a 384-dim embedding vector via `SentenceTransformer("all-MiniLM-L6-v2").encode(claim)`
2. ChromaDB performs HNSW-based ANN search, returning the top-20 nearest documents by cosine distance
3. Cosine distance is converted to cosine similarity: `similarity = 1 - distance`
4. An **access-count boost** is applied: `boosted_score = similarity + (access_count * 0.02)`
5. Results are sorted by boosted score in descending order

**Access-count boosting explained**: Each time a document is retrieved and passes the reranking threshold (i.e., it is actually relevant), its `access_count` metadata field is incremented by 1. On subsequent queries, each access adds a `0.02` score bonus. This means a document accessed 10 times gets a `+0.20` boost. This creates a positive feedback loop: frequently relevant evidence rises in ranking over time, making the system progressively better at surfacing high-quality evidence.

**Important**: Access counts are ONLY incremented for documents that pass the cross-encoder reranking threshold (Step 3). This prevents irrelevant documents from accumulating false popularity.

### Step 3: Cross-Encoder Reranking

**Files**: `agent.py` — `_retrieve_kb()`, `reranker.py` — `rerank()`

The top-20 candidates from Step 2 are re-scored using a cross-encoder model that considers the claim and each evidence text jointly, rather than independently.

**Why reranking is necessary**: Bi-encoder models (like all-MiniLM-L6-v2) encode the query and documents independently, which is fast but can miss nuanced relevance. A cross-encoder takes the claim-evidence pair as a single input, allowing full attention between all tokens. This produces significantly more accurate relevance scores at the cost of being slower (O(n) inference vs O(1) lookup).

**Reranking process:**

1. Create pairs: `[(claim, evidence_1_text), (claim, evidence_2_text), ...]`
2. The cross-encoder (`ms-marco-MiniLM-L-6-v2`, max sequence length 512 tokens) scores each pair
3. Candidates with score below `MIN_RELEVANCE_SCORE` (0.3) are filtered out entirely
4. Remaining candidates are sorted by score and the top-5 are returned

**Threshold filtering**: If ALL candidates score below 0.3, an empty list is returned. This prevents low-quality evidence from reaching the verdict stage, which would lead to unreliable verdicts.

### Step 4: Sufficiency Check

**File**: `agent.py` — `_has_enough_evidence()`

The agent decides whether the KB evidence alone is sufficient to verify the claim, or whether a web search is needed. This is a three-tier gate:

1. **Quantity check**: At least 2 pieces of evidence are required. A single source is not enough for verification.
2. **Quality check**: The average rerank score across all evidence must be >= 1.0. Low-scoring evidence, even in quantity, is not sufficient.
3. **LLM judgment**: GPT-4o-mini receives the claim and the top-5 evidence pieces (with their relevance scores) and answers a simple "yes" or "no" to whether the evidence is sufficient and directly relevant.

All three conditions must pass for the agent to skip web search. If any condition fails, the agent proceeds to web search.

### Step 5: Multi-Stage Web Search (Conditional)

**Files**: `agent.py` — `_search_and_index()`, `web_search.py`

When KB evidence is insufficient, the agent executes up to three web search stages with rate-limit protection between each stage.

#### Stage 5a: Trusted News Search

- Uses DuckDuckGo with a domain filter restricting results to the top 4 trusted domains: `reuters.com`, `bbc.com`, `apnews.com`, `nytimes.com`
- Query format: `{claim} (site:reuters.com OR site:bbc.com OR site:apnews.com OR site:nytimes.com)`
- Returns up to 8 results
- All results are immediately indexed into ChromaDB (ever-growing KB)
- A 2-second delay follows to avoid DuckDuckGo rate-limiting

#### Stage 5b: Fact-Checker Search

- Targets dedicated fact-checking sites: `snopes.com`, `factcheck.org`, `politifact.com`
- Query format: `{claim} (site:snopes.com OR site:factcheck.org OR site:politifact.com)`
- Returns up to 5 results
- All results are indexed into ChromaDB

#### Stage 5c: Broad Web Search (Conditional Fallback)

- Only triggered if the total relevant evidence (KB + trusted + fact-checker) is still fewer than 2 pieces
- Uses unrestricted DuckDuckGo search (no domain filter)
- Returns up to 8 results
- A 2-second delay precedes this stage
- All results are indexed into ChromaDB

**Rate-limit protection**: DuckDuckGo can rate-limit aggressive queries. The `search_web()` function includes exponential backoff retry logic with delays of 2s, 5s, and 10s across up to 3 retries. It also uses browser-like User-Agent headers to reduce the chance of being blocked.

**Automatic KB indexing**: Every web search result (snippet, URL, title) is immediately batch-indexed into ChromaDB via `add_documents_batch()`. This is the core mechanism of the ever-growing knowledge base. The next time a similar claim is verified, the system may find the answer in its KB without needing a web search.

### Step 6: Deduplication and Final Reranking

**Files**: `agent.py` — `_deduplicate()`, `_rerank_evidence()`, `reranker.py` — `rerank_with_credibility()`

#### Deduplication

Before the final rerank, near-duplicate evidence is removed. Two pieces of evidence are considered duplicates if:
- They share the same source URL, OR
- The first 100 characters of their text (lowercased) match

#### Multi-Stage Reranking with Source Credibility

The final reranking uses an enhanced pipeline that goes beyond pure relevance:

1. **Cross-encoder relevance scoring**: Same as Step 3 — each claim-evidence pair is scored
2. **Source credibility lookup**: The domain is extracted from the source URL and looked up in the `SOURCE_CREDIBILITY` dictionary (see [Section 6](#6-source-credibility-system))
3. **Combined scoring**:
   ```
   credibility_boost = (credibility_score - 0.5) * CREDIBILITY_BOOST_FACTOR
   final_score = relevance_score + credibility_boost
   ```
   Where `CREDIBILITY_BOOST_FACTOR = 0.3`. This means:
   - A source with credibility 0.95 (e.g., Reuters) gets a `+0.135` boost
   - A source with credibility 0.5 (unknown domain) gets `+0.0` boost (neutral)
   - A source with credibility 0.3 (if any) would get a `-0.06` penalty
4. **Source diversity enforcement**: A maximum of 2 results from the same domain are allowed. This prevents a single source from dominating the evidence list.
5. **Threshold filtering**: Evidence with a relevance score (pre-credibility) below 0.3 is removed
6. **Top-5 selection**: The final sorted, diverse, credibility-adjusted list is truncated to 5

### Step 7: LLM Verdict Generation

**File**: `agent.py` — `_generate_verdict()`

The top evidence (filtered to only those with score > 0.0) is formatted into a numbered evidence block and sent to GPT-4o-mini for verdict generation.

**Evidence format sent to LLM:**
```
[1] (Source: https://reuters.com/..., Origin: web, Relevance: 4.23)
Reuters reports that the Earth is an oblate spheroid...

[2] (Source: https://nasa.gov/..., Origin: kb, Relevance: 3.89)
The Earth is approximately 4.54 billion years old...
```

**LLM constraints (enforced via system prompt):**
- MUST cite evidence using `[1]`, `[2]`, etc. matching the evidence numbers
- MUST NOT fabricate sources or evidence not in the provided list
- MUST only use evidence that DIRECTLY addresses the specific claim
- If evidence is contradictory, must explain both sides
- If evidence is insufficient, verdict MUST be "Not Enough Evidence"
- Output MUST be valid JSON with: `verdict`, `confidence` (0-1 float), `reasoning`

**LLM parameters:**
- Model: `gpt-4o-mini`
- Temperature: `0.1` (near-deterministic but allowing slight variation)
- Max tokens: `1000`
- Response format: `{"type": "json_object"}` (guaranteed valid JSON)

**No-evidence fallback**: If all evidence has been filtered out (all scores <= 0.0), the system returns "Not Enough Evidence" without calling the LLM. This prevents hallucination when there is genuinely no evidence.

### Context Isolation

**File**: `agent.py` — `verify()` method

Each call to `verify()` generates a fresh UUID (`uuid.uuid4()`) as the session ID. There is:
- No conversation history carried between verification calls
- No memory of previous claims
- No shared state between sessions

This prevents the well-known issue where sequential LLM calls in a shared conversation context cause previous claims to influence new ones. Each verification is fully independent.

---

## 3. Core Components — Detailed Technical Reference

### 3.1 Claim Verifier Agent (`agent.py`)

The `ClaimVerifier` class is the central orchestrator. It holds references to all subsystems and implements the agentic decision loop.

**Data classes:**

```python
@dataclass
class Evidence:
    text: str          # Evidence text content
    source: str        # Source URL
    score: float       # Relevance score (from reranker)
    origin: str        # "kb" | "web" | "fact_check"

@dataclass
class VerificationResult:
    claim: str              # Normalised/extracted claim
    verdict: str            # One of VERDICTS list
    confidence: float       # 0.0 - 1.0
    reasoning: str          # LLM-generated reasoning with [N] citations
    evidence: list[Evidence]  # Ranked evidence used
    steps: list[str]        # Agent trace log
    session_id: str         # UUID for this verification session
    claim_type: str         # FACTUAL / OPINION / MIXED / AMBIGUOUS
    original_claim: str     # User's raw input before normalisation
```

**Public API:**
- `verify(raw_claim: str) -> VerificationResult` — End-to-end verification. This is the only method external code needs to call.

**Internal methods:**

| Method | Purpose |
|---|---|
| `_extract_and_classify_claim(raw)` | LLM-based claim classification and extraction |
| `_retrieve_kb(claim)` | Semantic search + rerank from ChromaDB |
| `_has_enough_evidence(claim, evidence)` | Three-tier sufficiency gate |
| `_search_and_index(claim, search_fn)` | Execute a search function and index results into KB |
| `_rerank_evidence(claim, evidence)` | Final multi-stage reranking with credibility |
| `_deduplicate(evidence)` | Remove near-duplicate evidence |
| `_generate_verdict(claim, evidence)` | LLM-based verdict with citations |

### 3.2 Vector Store (`vector_store.py`)

The `VectorStore` class wraps ChromaDB and provides document indexing, semantic retrieval, and metadata management.

**Initialisation:**
- Creates a `SentenceTransformer("all-MiniLM-L6-v2")` embedder (384 dimensions)
- Connects to a persistent ChromaDB client at `./chroma_db/`
- Gets or creates a collection named `"news_evidence"` with HNSW index using cosine distance

**Key methods:**

| Method | Signature | Purpose |
|---|---|---|
| `add_document()` | `(text, source, details, timestamp, source_type) -> str` | Index a single document with full metadata |
| `add_documents_batch()` | `(docs: list[dict]) -> list[str]` | Batch-index multiple documents |
| `query()` | `(claim, top_k=20) -> list[dict]` | Semantic search with access-count boosting |
| `increment_access()` | `(doc_id: str)` | Bump `access_count` metadata by 1 |
| `count()` | `() -> int` | Total documents in the collection |

**Document ID generation:**
```python
doc_id = f"doc_{int(time.time()*1000)}_{hash(text) % 100000}"
```
IDs combine a millisecond timestamp with a hash of the text content, ensuring uniqueness while being somewhat deterministic for the same content.

**Internal helpers:**
- `_extract_domain(url)` — Parses URL, removes `www.` prefix, returns domain (e.g., `reuters.com`)
- `_infer_source_type(domain)` — Classifies domain into `fact_checker`, `government`, `academic`, `news`, or `unknown`

### 3.3 Reranker (`reranker.py`)

The `Reranker` class provides two reranking methods — one for basic relevance and one with source credibility integration.

**Model:** `cross-encoder/ms-marco-MiniLM-L-6-v2` with max sequence length of 512 tokens.

**Methods:**

| Method | Use Case |
|---|---|
| `rerank(claim, candidates, top_k)` | Basic cross-encoder reranking (used for initial KB retrieval in Step 3) |
| `rerank_with_credibility(claim, candidates, top_k)` | Multi-stage reranking with credibility scoring and diversity enforcement (used for final reranking in Step 6) |

**`rerank_with_credibility` pipeline detail:**

```
Input candidates
       |
       v
[Cross-Encoder Scoring] --> rerank_score per candidate
       |
       v
[Domain Extraction] --> extract domain from source URL
       |
       v
[Credibility Lookup] --> SOURCE_CREDIBILITY dict (default 0.5)
       |
       v
[Combined Scoring] --> final_score = rerank_score + (credibility - 0.5) * 0.3
       |
       v
[Sort by final_score descending]
       |
       v
[Filter: rerank_score >= 0.3]  (note: filter is on raw relevance, not final_score)
       |
       v
[Diversity: max 2 per domain]
       |
       v
[Return top-K]
```

### 3.4 Web Search (`web_search.py`)

Three specialised search functions, all built on DuckDuckGo:

| Function | Domain Filter | Max Results | Purpose |
|---|---|---|---|
| `search_web(query)` | None (unrestricted) | 8 | General fallback search |
| `search_trusted(query)` | reuters, bbc, apnews, nytimes | 8 | High-quality news evidence |
| `search_fact_checkers(claim)` | snopes, factcheck.org, politifact | 5 | Dedicated fact-checking evidence |

**Rate-limit protection:**
- Browser-like `User-Agent` header (Chrome on macOS)
- Exponential backoff: 3 retries with delays of 2s, 5s, 10s
- Only retries on `Ratelimit` errors; other errors fail immediately

**Return format:** Each function returns `list[dict]` with keys: `title`, `snippet`, `url`.

### 3.5 Configuration (`config.py`)

All tuneable parameters are centralised in `config.py`. Environment variables are loaded from `.env` via `python-dotenv`.

---

## 4. Metadata Schema — Design, Fields, and Usage

Every document stored in ChromaDB carries a rich metadata record. This metadata serves multiple purposes: evidence quality assessment, source credibility scoring, usage tracking, and system observability.

### Complete Metadata Field Reference

| Field | Type | Default | Description | How It Is Used |
|---|---|---|---|---|
| `source` | `string` | `""` | Full URL of the evidence source | Displayed in UI as clickable link; used for deduplication; domain extracted for credibility lookup |
| `source_type` | `string` | `"unknown"` | Category: `news`, `academic`, `fact_checker`, `government`, `unknown` | Inferred from domain via `_infer_source_type()`. Used for UI display and future filtering |
| `source_credibility` | `float` | `0.5` | Credibility score (0.0 to 1.0) | Looked up from `SOURCE_CREDIBILITY` dict by domain. Used in `rerank_with_credibility()` to compute credibility boost: `(credibility - 0.5) * 0.3` |
| `details` | `string` | `""` | Human-readable description (typically the article title) | Displayed in UI evidence cards |
| `timestamp` | `string` | Auto-generated ISO 8601 | When the document was indexed (e.g., `2025-01-15T10:30:00Z`) | Used for temporal tracking; future use for recency-based scoring |
| `access_count` | `int` | `0` | Number of times this document was retrieved AND passed the relevance threshold | Incremented via `increment_access()`. Used in query scoring: `boosted_score = similarity + (access_count * 0.02)` |
| `verification_count` | `int` | `0` | Number of times this document was used in a final verdict | Reserved for future use — tracking which evidence contributes to verdicts |
| `avg_relevance` | `float` | `0.0` | Average cross-encoder relevance score across all uses | Reserved for future use — tracking evidence quality over time |
| `last_accessed` | `string` | Same as `timestamp` | ISO 8601 timestamp of last retrieval | Set at creation time; reserved for future temporal decay weighting |
| `domain` | `string` | Extracted from `source` | Domain name (e.g., `reuters.com`, `nasa.gov`) | Used in diversity enforcement (max 2 per domain) and credibility lookup |
| `text_length` | `int` | `len(text)` | Character count of the evidence text | Used for observability; potential future use for length-based filtering |
| `language` | `string` | `"en"` | Content language | Default English; reserved for future multilingual support |

### How Metadata Is Populated

**At indexing time** (when a new document enters the KB):

1. `source` — Provided by the caller (web search URL or seed fact URL)
2. `domain` — Automatically extracted from `source` via `_extract_domain(url)`, which parses the URL and strips the `www.` prefix
3. `source_type` — Automatically inferred from `domain` via `_infer_source_type()`:
   - Checks against known fact-checker domains (`snopes.com`, `factcheck.org`, `politifact.com`, `fullfact.org`)
   - Checks for `.gov` / `.gov.uk` suffixes or known government/scientific domains (`who.int`, `cdc.gov`, `nasa.gov`, `nih.gov`)
   - Checks for known academic domains (`arxiv.org`, `nature.com`, `science.org`) or `.edu` suffix
   - Falls back to `"news"` if domain exists in `SOURCE_CREDIBILITY` with score >= 0.7
   - Otherwise `"unknown"`
4. `source_credibility` — Looked up from `SOURCE_CREDIBILITY` dictionary in `config.py`. Unknown domains default to `0.5` (neutral).
5. `timestamp` — Auto-generated as UTC ISO 8601 if not provided
6. `access_count`, `verification_count`, `avg_relevance` — Initialised to 0
7. `last_accessed` — Set to same value as `timestamp`
8. `text_length` — Computed as `len(text)`
9. `language` — Defaults to `"en"`

**At retrieval time** (when a document matches a query):

1. `access_count` — Incremented by 1 via `increment_access()`, but ONLY after the document passes cross-encoder reranking (score >= 0.3). This prevents irrelevant matches from inflating their popularity.

### Metadata in the Retrieval Pipeline

The metadata fields participate in the retrieval pipeline at several points:

```
[Query] --> ChromaDB HNSW Search
                |
                | returns: text, source, details, timestamp, access_count, cosine_distance
                |
                v
         [Access-Count Boosting]
              boosted_score = (1 - cosine_distance) + (access_count * 0.02)
                |
                v
         [Cross-Encoder Reranking]
              (uses text only — metadata not involved here)
                |
                v
         [Increment Access Count]
              Only for documents that pass MIN_RELEVANCE_SCORE (0.3)
                |
                v
         [Final Reranking with Credibility]
              domain extracted from source URL
              credibility = SOURCE_CREDIBILITY.get(domain, 0.5)
              final_score = relevance + (credibility - 0.5) * 0.3
                |
                v
         [Diversity Enforcement]
              Max 2 results per domain
```

### Metadata Migration Compatibility

The metadata schema was expanded in v2.0. Old documents that were indexed before the schema expansion continue to work because:
- All new fields have sensible defaults (`0`, `0.0`, `""`, `"unknown"`, `"en"`)
- The `meta.get("field", default)` pattern is used throughout the codebase
- No migration script is needed — new fields are simply absent from old records and defaults are used

---

## 5. Knowledge Base Design — Ever-Growing Architecture

The knowledge base follows an **ever-growing** design pattern. It starts with a small set of seed facts and automatically expands with every verification that triggers a web search.

### Seed Knowledge Base

**File**: `seed_kb.py`

On first run, both `app.py` and `api.py` call `seed()`, which checks if the KB is empty and, if so, indexes 10 verified facts covering:

| Topic | Source |
|---|---|
| Earth's age (4.54 billion years) | NASA |
| Earth's shape (oblate spheroid, not flat) | NASA |
| COVID-19 vaccine safety | WHO |
| Moon landing (Apollo 11, 1969) | NASA |
| Climate change scientific consensus | NASA |
| 5G and health (no link to COVID) | WHO |
| Water fluoridation safety | CDC |
| Speed of light | NIST |
| India's independence (1947) | Britannica |
| United Nations founding (1945) | UN |

These seed facts ensure the system can immediately verify common claims without requiring web access.

### Dynamic Growth Mechanism

Every time the system performs a web search (Steps 5a, 5b, 5c), ALL returned results are indexed into ChromaDB via `add_documents_batch()`. This means:

1. **First verification of "Earth is flat"**: KB has seed fact about Earth's shape. May still trigger web search for additional evidence. Web results are indexed.
2. **Second verification of "Earth is flat"**: KB now contains the original seed fact PLUS all web results from the first verification. More evidence is available, the sufficiency check may pass, and web search may be skipped entirely.
3. **Related claim "Earth is round"**: Benefits from all evidence previously indexed about Earth's shape, even though the exact wording differs (semantic search handles this).

### Access-Count Popularity Signal

Documents that are frequently relevant to user queries naturally accumulate higher `access_count` values. The `0.02` boost per access creates a gentle preference for battle-tested evidence. After 25 accesses, a document receives a `+0.50` similarity boost — significant enough to push it ahead of slightly closer but less-proven evidence.

This approximates a "wisdom of the crowd" signal: if many different claims have found a piece of evidence relevant, it is likely high-quality and broadly applicable.

---

## 6. Source Credibility System

The source credibility system assigns a trust score (0.0 to 1.0) to each known domain. These scores affect the final reranking but do NOT override relevance — a highly relevant result from an unknown source can still outrank a less relevant result from a trusted source.

### Credibility Tiers

| Tier | Score Range | Domains | Rationale |
|---|---|---|---|
| **Fact-Checkers** | 0.90 - 0.95 | snopes.com, factcheck.org, politifact.com, fullfact.org | Dedicated fact-checking organisations with editorial standards |
| **Government/Scientific** | 0.95 | who.int, cdc.gov, nasa.gov, nih.gov, gov.uk | Authoritative government and international scientific bodies |
| **News Agencies** | 0.85 - 0.90 | reuters.com, apnews.com, bbc.com, npr.org, pbs.org | Wire services and public broadcasters with strong editorial oversight |
| **Major Newspapers** | 0.80 | nytimes.com, washingtonpost.com, theguardian.com, wsj.com | Established newspapers with editorial review processes |
| **Academic** | 0.80 - 0.90 | nature.com, science.org, arxiv.org, scholar.google.com | Peer-reviewed and academic publications |
| **International News** | 0.75 | aljazeera.com, dw.com, france24.com | Reputable international news outlets |
| **Unknown** | 0.50 | Any domain not in the list | Neutral — neither boosted nor penalised |

### Credibility Boost Formula

```
credibility_boost = (source_credibility - 0.5) * CREDIBILITY_BOOST_FACTOR
final_score = cross_encoder_relevance + credibility_boost
```

Where `CREDIBILITY_BOOST_FACTOR = 0.3`.

**Impact examples:**

| Source | Credibility | Boost | Effect |
|---|---|---|---|
| reuters.com | 0.90 | +0.12 | Moderate positive boost |
| snopes.com | 0.95 | +0.135 | Strongest positive boost |
| unknown-blog.com | 0.50 | +0.0 | No effect (neutral) |
| nature.com | 0.90 | +0.12 | Moderate positive boost |

The boost is additive to the cross-encoder score, which typically ranges from -10 to +10. A +0.135 boost is meaningful but not overwhelming — it can break ties between similarly relevant evidence but cannot elevate irrelevant evidence.

---

## 7. Claim Classification System

The claim classification system prevents the pipeline from wasting compute on non-verifiable input.

### Classification Prompt Design

The LLM receives a detailed system prompt with explicit classification rules and examples for each category. Key design principles:

1. **Preserve errors**: "India is a company" is classified as FACTUAL, not corrected. The verification pipeline should reveal the error through evidence.
2. **Extract factual parts from mixed claims**: "Minecraft is the best 2D game" becomes "Minecraft is a 2D game" — the subjective "best" is discarded, the factual claim about being 2D is preserved.
3. **Never verify opinions**: Pure opinions like "Pizza tastes better than burgers" are rejected immediately with a clear explanation.
4. **Structured JSON output**: The LLM returns `{"type": "...", "claim": "...", "reasoning": "..."}` using OpenAI's JSON mode.

### Claim Type Handling

| Type | Pipeline Response | User Feedback |
|---|---|---|
| FACTUAL | Full pipeline execution | Normal verification result |
| OPINION | Immediate return, no retrieval | "This appears to be a subjective opinion. Opinions cannot be fact-checked." |
| MIXED | Extract factual part, verify that | Shows both "Original Input" and "Extracted Claim" in UI |
| AMBIGUOUS | Immediate return, no retrieval | "The claim is too ambiguous. Please rephrase with more specific details." |

---

## 8. Verdict Types and Decision Logic

The system produces one of six verdict types:

| Verdict | Emoji | Meaning | When Issued |
|---|---|---|---|
| **True** | ✅ | Claim is supported by evidence | Multiple credible sources confirm the claim |
| **False** | ❌ | Claim is contradicted by evidence | Multiple credible sources contradict the claim |
| **Partially True** | ⚠️ | Mixed support and contradiction | Some aspects are correct, others are not |
| **Misleading** | 🟠 | Technically true but deceptive | Claim is worded in a way that creates a false impression |
| **Not Enough Evidence** | ❓ | Cannot verify with available evidence | Insufficient or insufficiently relevant evidence found |
| **Not Verifiable** | 💬 | Claim is subjective or ambiguous | Claim is an opinion (OPINION) or too vague (AMBIGUOUS) |

### Confidence Score

The LLM assigns a confidence score between 0.0 and 1.0 alongside the verdict. This reflects how confident the system is in its judgment based on the available evidence. The confidence is displayed as a percentage with a visual progress bar in the UI.

### Safety Constraints

The system is designed to never fabricate:
- If no relevant evidence exists (all scores <= 0.0), the system returns "Not Enough Evidence" WITHOUT calling the LLM
- The LLM is explicitly instructed to ONLY cite evidence from the provided list
- The LLM is told to be "skeptical of low-scoring evidence"
- If the LLM JSON response fails to parse, the system defaults to "Not Enough Evidence"

---

## 9. User Interfaces

### 9.1 Streamlit Web UI (`app.py`)

The primary interface is a Streamlit web application with custom CSS styling.

**Features:**
- Text area for free-form claim input
- 5 pre-built example claims as quick-select buttons
- Colour-coded verdict cards (green for True, red for False, yellow for Partial, orange for Misleading, grey for Not Enough Evidence)
- Confidence bar with percentage display
- Claim type badges (FACTUAL, OPINION, MIXED, AMBIGUOUS) with colour coding
- Display of both original input and extracted claim for MIXED types
- Expandable evidence cards with origin badge (Knowledge Base / Web Source / Fact-Checker), relevance score, and credibility stars
- Agent trace log showing each pipeline step
- Sidebar with: KB document count, pipeline step-by-step explanation, tech stack pills

**Auto-seeding**: On first load, `init_system()` calls `seed()` and creates a `ClaimVerifier` instance, both cached via `@st.cache_resource`.

### 9.2 Flask REST API (`api.py`)

A lightweight REST API for programmatic access and Chrome Extension integration.

**Endpoints:**

| Endpoint | Method | Request | Response |
|---|---|---|---|
| `/api/verify` | POST | `{"claim": "The Earth is flat"}` | Full verification result (JSON) |
| `/api/health` | GET | — | `{"status": "ok", "kb_size": 42}` |

**Verify response fields:**

```json
{
  "claim": "The Earth is flat",
  "verdict": "False",
  "confidence": 0.95,
  "reasoning": "Multiple authoritative sources [1][2] confirm that...",
  "evidence": [
    {
      "text": "The Earth is an oblate spheroid...",
      "source": "https://www.nasa.gov/solar-system/earth/",
      "score": 4.231,
      "origin": "kb"
    }
  ],
  "steps": ["Step 1: Classifying...", "Step 2: Retrieving..."],
  "claim_type": "FACTUAL",
  "original_claim": "The Earth is flat",
  "session_id": "a1b2c3d4-..."
}
```

**CORS**: Enabled for all origins via `flask-cors`. This allows the Chrome Extension (running on any webpage domain) to communicate with the localhost API.

### 9.3 Chrome Extension (`chrome_extension/`)

A Manifest V3 Chrome Extension providing three verification methods:

**1. Floating Button (content.js)**
- User highlights text on any webpage
- A floating "Verify Claim" button appears near the selection
- Click triggers verification via the Flask API
- Results displayed in an overlay on the current page

**2. Right-Click Context Menu (background.js)**
- Select text on any page
- Right-click opens context menu with "Verify Claim" option
- Sends selected text to content script for API call

**3. Toolbar Popup (popup.html + popup.js)**
- Click extension icon in Chrome toolbar
- Type or paste a claim manually
- Submit for verification

**Architecture:**
```
Content Script (content.js)     Background Service Worker (background.js)
     |                                    |
     | -- "api-verify" message -->        |
     |                                    | -- POST /api/verify -->  Flask API
     |                                    | <-- JSON response ------
     | <-- sendResponse(data) ---         |
     |                                    |
     v                                    |
 Render result overlay                    |
```

**Permissions required:**
- `contextMenus` — for right-click menu
- `activeTab` — to access current tab content
- `storage` — for extension settings
- `host_permissions: http://localhost:5000/*` — to communicate with Flask API

---

## 10. Setup and Installation

### Prerequisites

- Python 3.9+
- An OpenAI API key (for GPT-4o-mini)

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd W1_RAG

# Install Python dependencies
pip install -r requirements.txt
```

### Dependencies

| Package | Version | Purpose |
|---|---|---|
| `streamlit` | 1.41.0 | Web UI framework |
| `openai` | 1.61.0 | GPT-4o-mini API client |
| `chromadb` | 0.6.3 | Vector database |
| `sentence-transformers` | 3.4.1 | Embedding and cross-encoder models |
| `duckduckgo-search` | 7.3.2 | Web search without API key |
| `newspaper3k` | 0.2.8 | Article extraction (optional) |
| `lxml[html_clean]` | 5.3.0 | HTML parsing for newspaper3k |
| `python-dotenv` | 1.0.1 | Environment variable loading from `.env` |
| `flask` | 3.1.0 | REST API framework |
| `flask-cors` | 5.0.0 | Cross-origin resource sharing for Chrome Extension |

### Environment Configuration

```bash
# Option 1: Environment variable
export OPENAI_API_KEY=sk-your-key-here        # macOS/Linux
set OPENAI_API_KEY=sk-your-key-here           # Windows

# Option 2: .env file in project root
echo "OPENAI_API_KEY=sk-your-key-here" > .env
```

### Running the Application

```bash
# 1. Streamlit Web UI (primary interface)
streamlit run app.py
# Opens at http://localhost:8501
# Auto-seeds the KB with 10 verified facts on first run

# 2. Flask API (required for Chrome Extension)
python api.py
# Runs on http://localhost:5000
# Also auto-seeds the KB on first run

# 3. Manual KB seeding (optional — happens automatically)
python seed_kb.py
```

### Chrome Extension Setup

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable **Developer mode** (toggle in top-right)
3. Click **Load unpacked** and select the `chrome_extension/` folder
4. Ensure the Flask API is running (`python api.py`)
5. **Usage options:**
   - Highlight text on any webpage and click the floating "Verify Claim" button
   - Right-click selected text and choose "Verify Claim" from the context menu
   - Click the extension icon in the toolbar to type a claim manually

---

## 11. Project Structure

```
W1_RAG/
|
|-- agent.py                   # Core: Agentic RAG verification pipeline (ClaimVerifier class)
|-- vector_store.py            # Core: ChromaDB wrapper with metadata management (VectorStore class)
|-- reranker.py                # Core: Cross-encoder reranking with credibility (Reranker class)
|-- web_search.py              # Core: DuckDuckGo search functions (trusted, fact-checker, broad)
|-- config.py                  # Config: All constants, thresholds, domain lists, credibility scores
|
|-- app.py                     # UI: Streamlit web application
|-- api.py                     # API: Flask REST backend for Chrome Extension
|
|-- seed_kb.py                 # Setup: Seeds initial knowledge base with 10 verified facts
|-- generate_icons.py          # Setup: Generates PNG icons for Chrome Extension
|
|-- requirements.txt           # Dependencies
|-- .env.example               # Environment variable template
|-- README.md                  # This document
|
|-- chroma_db/                 # Data: ChromaDB persistent storage (auto-created, gitignored)
|
|-- chrome_extension/          # Chrome Extension (Manifest V3)
|   |-- manifest.json          #   Extension manifest
|   |-- background.js          #   Service worker (context menu, API routing)
|   |-- content.js             #   Content script (floating button, result overlay)
|   |-- content.css            #   Content script styles
|   |-- popup.html             #   Toolbar popup UI
|   |-- popup.js               #   Popup logic
|   |-- icons/                 #   Extension icons (generated by generate_icons.py)
```

---

## 12. Configuration Reference

All configurable parameters in `config.py`:

### LLM Settings

| Parameter | Value | Description |
|---|---|---|
| `LLM_MODEL` | `"gpt-4o-mini"` | OpenAI model used for classification, sufficiency, and verdict |
| `LLM_TEMPERATURE` | `0.1` | Low temperature for near-deterministic outputs |

### Embedding and Reranking

| Parameter | Value | Description |
|---|---|---|
| `EMBEDDING_MODEL` | `"all-MiniLM-L6-v2"` | Sentence-transformers model (384-dim embeddings) |
| `EMBEDDING_DIM` | `384` | Embedding vector dimensionality |
| `RERANKER_MODEL` | `"cross-encoder/ms-marco-MiniLM-L-6-v2"` | Cross-encoder for precision reranking |

### Retrieval Parameters

| Parameter | Value | Description |
|---|---|---|
| `TOP_K_RETRIEVAL` | `20` | Number of candidates from initial semantic search |
| `TOP_K_RERANK` | `5` | Number of results after cross-encoder reranking |
| `MIN_RELEVANCE_SCORE` | `0.3` | Minimum cross-encoder score to keep evidence |
| `CREDIBILITY_BOOST_FACTOR` | `0.3` | Maximum credibility score adjustment in final reranking |

### Web Search

| Parameter | Value | Description |
|---|---|---|
| `MAX_SEARCH_RESULTS` | `8` | Maximum results per web search call |
| `TRUSTED_DOMAINS` | 15 domains | Domains used by `search_trusted()` (reuters, bbc, ap, etc.) |

### Storage

| Parameter | Value | Description |
|---|---|---|
| `CHROMA_PERSIST_DIR` | `"./chroma_db"` | Directory for ChromaDB persistent storage |
| `COLLECTION_NAME` | `"news_evidence"` | ChromaDB collection name |

### Other

| Parameter | Value | Description |
|---|---|---|
| `TEMPORAL_DECAY_DAYS` | `365` | Evidence older than this gets reduced weight (reserved for future use) |

---

## 13. Development Guide

### Adding New Seed Facts

Edit the `SEED_FACTS` list in `seed_kb.py`. Each fact requires:

```python
{
    "text": "The factual statement to verify against.",
    "source": "https://authoritative-source.com/page",
    "details": "Human-readable source description (e.g., 'NASA - Earth Facts')",
}
```

To re-seed: delete the `./chroma_db/` directory and restart the application.

### Adjusting Retrieval Quality

- **More candidates**: Increase `TOP_K_RETRIEVAL` (default 20) to consider more initial matches
- **More final evidence**: Increase `TOP_K_RERANK` (default 5) to show more evidence to the LLM
- **Stricter filtering**: Increase `MIN_RELEVANCE_SCORE` (default 0.3) to reject more borderline evidence
- **Stronger credibility effect**: Increase `CREDIBILITY_BOOST_FACTOR` (default 0.3) to weight trusted sources more heavily

### Adding Trusted Domains

Add domains to `TRUSTED_DOMAINS` in `config.py` (used by `search_trusted()`) and optionally add credibility scores to `SOURCE_CREDIBILITY`.

### Modifying LLM Prompts

Three system prompts control LLM behaviour, all in `agent.py`:

1. **Claim classification** (`_extract_and_classify_claim`): Controls how claims are categorised and factual components are extracted
2. **Sufficiency check** (`_has_enough_evidence`): Controls the threshold for "enough evidence"
3. **Verdict generation** (`_generate_verdict`): Controls how the final verdict, reasoning, and citations are produced

### Resetting the Knowledge Base

Delete the `./chroma_db/` directory. On the next application start, the system will create a fresh collection and re-seed with the 10 default facts.

### Debugging Agent Decisions

The `VerificationResult.steps` field contains the complete agent trace. In the Streamlit UI, expand the "Agent Trace" section to see:
- What claim type was detected
- How many KB evidence pieces were found
- Whether the sufficiency check passed or failed
- How many web search results were found at each stage
- How many total evidence pieces were reranked

---

## Constraints and Limitations

- **OpenAI API key required**: The system cannot function without a valid `OPENAI_API_KEY`
- **DuckDuckGo rate limits**: Heavy usage may trigger rate limiting. The system handles this with exponential backoff but extended outages are possible
- **English-only**: The system defaults to English language. Metadata `language` field exists for future multilingual support
- **Snippet-level evidence**: Web search results are snippets (1-3 sentences), not full articles. This is by design for atomic evidence storage
- **No real-time updates**: The KB grows only when verifications trigger web searches. There is no background ingestion pipeline
- **Chrome Extension requires localhost**: The extension communicates with `http://localhost:5000` (hardcoded in `background.js`). This must be changed for production deployment
- **CORS wide open**: The Flask API allows all origins (`CORS(app)`). Restrict this in production
