# Indian Financial Intelligence MCP Server
## Complete task breakdown & engineering plan

**Tech lead directive**: This document is the single source of truth for the entire build. Every team member reads this before writing a single line of code. No code in this document — only architecture decisions, task assignments, standards, and sequencing.

---

## Technology decisions (final)

| Layer | Technology | Why |
|---|---|---|
| MCP server | **Python 3.12 + FastMCP** | Best MCP SDK maturity, CrewAI native, rich financial library ecosystem |
| Auth server | **Keycloak 24.x** (Docker) | OAuth 2.1 + PKCE out of the box, free, MCP spec recommended |
| Frontend dashboard | **Next.js 14 + TypeScript + Tailwind** | SSR for SEO, App Router for tabs/routes, shadcn/ui for speed |
| LLM provider | **OpenAI (GPT-4o + GPT-4o-mini)** | Best tool-calling reliability, structured output support |
| Agent framework | **CrewAI** (Python) | Multi-agent orchestration, Pydantic output, hierarchical process |
| Tracing & observability | **LangSmith** (LangChain tracing) | Visual trace of every agent call, token usage, latency breakdown |
| Cache | **Redis 7** | TTL-based caching, rate limit counters, pub/sub for subscriptions |
| Database | **PostgreSQL 16** | User data, watchlists, portfolios, audit logs, cached research |
| Deployment | **Docker Compose** | Single command: MCP + Keycloak + Redis + Postgres + Frontend |
| MCP clients | **Claude Desktop, VS Code, Windsurf** | Multi-client demo required by rubric |

---

## Architecture overview (what we decided)

```
┌─────────────────────────────────────────────────────────────────┐
│  FRONTEND (Next.js + TypeScript)                                │
│  Tab 1: PS1 Research Copilot                                    │
│  Tab 2: PS2 Portfolio Risk Monitor                              │
│  Tab 3: PS3 Earnings Command Center                             │
│  Auth: Keycloak JS adapter → OAuth 2.1 PKCE flow               │
└─────────────────────┬───────────────────────────────────────────┘
                      │ Streamable HTTP (MCP protocol)
┌─────────────────────▼───────────────────────────────────────────┐
│  MCP SERVER (Python + FastMCP)                                  │
│  ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌──────────────────┐  │
│  │ Tools    │ │Resources │ │ Prompts   │ │ Scope enforcer   │  │
│  │ (30+)   │ │ (URIs)   │ │ (templates│ │ (tier → scopes)  │  │
│  └──────────┘ └──────────┘ └───────────┘ └──────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ CrewAI Engine (4 agents + synthesizer per use case)      │   │
│  │ PS1: Research crew  │ PS2: Risk crew  │ PS3: Earnings crew│  │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Data Aggregation Facade                                  │   │
│  │ Adapters → Circuit breakers → Fallback chains → ISIN map │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────┬───────────────────────────────────────────┘
                      │
    ┌────────┬────────┼────────┬─────────┬──────────┐
    ▼        ▼        ▼        ▼         ▼          ▼
  Angel    MFapi   BSE      Finnhub   Alpha V.   RBI DBIE
  One      .in     India              (+GNews)
```

**Critical rule**: The MCP server is the ONLY backend. The Next.js frontend connects to it via MCP protocol (Streamable HTTP). The frontend does NOT call financial APIs directly. The frontend does NOT have its own API routes for data. Everything flows through MCP tools.

---

## All three use cases — same server, different routes

We are building ALL THREE use cases (PS1, PS2, PS3) as different "modes" within the same MCP server. The frontend renders them as three tabs. Each tab invokes different MCP tools/prompts.

| Tab | Use case | Primary MCP tools used | Primary CrewAI crew |
|---|---|---|---|
| Research Copilot | PS1 | `cross_reference_signals`, `generate_research_brief`, `compare_companies` | Research crew (5 agents) |
| Portfolio Monitor | PS2 | `portfolio_risk_report`, `what_if_analysis`, `check_mf_overlap` | Risk crew (4 agents) |
| Earnings Center | PS3 | `earnings_verdict`, `earnings_season_dashboard`, `compare_quarterly_performance` | Earnings crew (4 agents) |

**Shared tools** (used by all tabs): `get_stock_quote`, `get_price_history`, `get_index_data`, `get_top_gainers_losers`, `get_company_news`, `get_news_sentiment`, `get_rbi_rates`, `search_mutual_funds`, `get_fund_nav`

---

## Skills required (skills.md)

Every team member should self-assess against this matrix. Assign tasks based on strengths.

### Skill 1: Python backend engineering
- FastAPI / async Python patterns
- Pydantic models for input/output validation
- Environment variable management, secrets handling
- Writing clean, type-annotated Python (use `mypy` strict mode)
- Understanding of adapter pattern, circuit breaker pattern, facade pattern

### Skill 2: MCP protocol knowledge
- Understanding of Tools vs Resources vs Prompts (when to use which)
- Streamable HTTP transport implementation
- Capability negotiation and tier-aware tool discovery
- Structured error responses (401, 403, 429 with proper headers)
- Session management via `Mcp-Session-Id` headers

### Skill 3: OAuth 2.1 + security
- OAuth 2.1 with PKCE flow (code challenge + verifier)
- JWT token validation (signature, expiry, audience, scopes)
- Keycloak realm configuration (clients, roles, scopes, mappers)
- Protected Resource Metadata (RFC 9728) — `.well-known` endpoint
- Understanding of Resource Server pattern (auth server separate from resource server)

### Skill 4: CrewAI / LLM agent engineering
- Agent design (role, goal, backstory — precise prompting)
- Custom tool creation (extending `BaseTool`)
- Sequential vs hierarchical process selection
- Pydantic output validation on tasks
- Prompt engineering for financial analysis (avoiding hallucinated numbers)
- Temperature tuning per agent type

### Skill 5: Frontend (Next.js + TypeScript)
- Next.js 14 App Router (not Pages Router)
- TypeScript strict mode
- Tailwind CSS + shadcn/ui component library
- MCP client SDK integration (connecting frontend to MCP server)
- Keycloak JS adapter for OAuth flow in browser
- Responsive design, dark mode support
- Data visualization (charts for price history, portfolio allocation)

### Skill 6: Financial domain knowledge
- Indian stock market basics (NSE/BSE, Nifty, Sensex)
- Fundamental analysis metrics (P/E, P/B, ROE, ROCE, debt/equity)
- Mutual fund terminology (NAV, AUM, expense ratio, scheme codes)
- SEBI regulations awareness (what constitutes "investment advice" vs "data tool")
- Earnings season workflow (pre-earnings, results, post-earnings reaction)

### Skill 7: DevOps & infrastructure
- Docker Compose multi-service orchestration
- Redis configuration and monitoring
- PostgreSQL schema design and migrations
- Environment variable templates (`.env.example`)
- Health check endpoints and upstream API status monitoring
- LangSmith tracing setup and dashboard interpretation

### Skill 8: API integration & data engineering
- REST API consumption with proper error handling
- Rate limit awareness and request throttling
- Web scraping (for BSE/NSE endpoints that lack official APIs)
- PDF parsing strategies (LLM-based extraction for BSE filings)
- Data normalization across different source formats
- ISIN-based cross-source symbol mapping

---

## Task breakdown — phase by phase

### Phase 0: Project setup (Day 1, first 2 hours)

**Task 0.1 — Repository and monorepo structure**
- Create GitHub repo with monorepo structure
- Set up branch protection: `main` (protected), `develop` (integration), feature branches
- Directory structure as follows:

```
/
├── mcp-server/           # Python MCP server
│   ├── src/
│   │   ├── server.py         # FastMCP entry point
│   │   ├── auth/             # OAuth middleware, token validation
│   │   ├── tools/            # All MCP tool implementations
│   │   │   ├── market/       # get_stock_quote, get_price_history, etc.
│   │   │   ├── fundamentals/ # get_financial_statements, get_key_ratios, etc.
│   │   │   ├── mutual_funds/ # search_mutual_funds, get_fund_nav, etc.
│   │   │   ├── news/         # get_company_news, get_news_sentiment, etc.
│   │   │   ├── macro/        # get_rbi_rates, get_inflation_data, etc.
│   │   │   ├── filings/      # get_corporate_filings, parse_quarterly_filing, etc.
│   │   │   ├── portfolio/    # PS2 tools: add_to_portfolio, risk checks, etc.
│   │   │   ├── earnings/     # PS3 tools: earnings_calendar, eps_history, etc.
│   │   │   └── cross_source/ # cross_reference_signals, research_brief, etc.
│   │   ├── resources/        # MCP resource implementations
│   │   ├── prompts/          # MCP prompt templates
│   │   ├── crews/            # CrewAI crew definitions
│   │   │   ├── research_crew.py    # PS1 agents
│   │   │   ├── risk_crew.py        # PS2 agents
│   │   │   └── earnings_crew.py    # PS3 agents
│   │   ├── data_facade/      # Adapter pattern, circuit breakers
│   │   │   ├── facade.py
│   │   │   ├── adapters/
│   │   │   │   ├── angel_one.py
│   │   │   │   ├── mfapi.py
│   │   │   │   ├── bse.py
│   │   │   │   ├── finnhub.py
│   │   │   │   ├── alpha_vantage.py
│   │   │   │   ├── rbi_dbie.py
│   │   │   │   ├── gnews.py
│   │   │   │   └── yfinance_adapter.py
│   │   │   ├── cache.py
│   │   │   ├── circuit_breaker.py
│   │   │   └── isin_mapper.py
│   │   ├── models/           # Pydantic models for all inputs/outputs
│   │   └── config/           # Settings, constants, TTL values
│   ├── tests/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── pyproject.toml
│
├── frontend/             # Next.js dashboard
│   ├── app/
│   │   ├── layout.tsx        # Root layout with tab navigation
│   │   ├── page.tsx          # Landing / auth gate
│   │   ├── research/         # PS1 tab
│   │   │   └── page.tsx
│   │   ├── portfolio/        # PS2 tab
│   │   │   └── page.tsx
│   │   ├── earnings/         # PS3 tab
│   │   │   └── page.tsx
│   │   └── settings/         # User tier, API status
│   │       └── page.tsx
│   ├── components/
│   ├── lib/
│   │   ├── mcp-client.ts     # MCP protocol client
│   │   └── auth.ts           # Keycloak integration
│   ├── Dockerfile
│   └── package.json
│
├── keycloak/             # Keycloak realm config
│   └── realm-export.json     # Pre-configured realm with tiers
│
├── docker-compose.yml    # Everything in one command
├── .env.example          # All required API keys with signup links
├── README.md             # Setup instructions
└── docs/
    ├── architecture.md
    ├── api-reference.md
    └── skills.md
```

**Task 0.2 — Environment and dependencies**
- Create `.env.example` with every required variable and signup URL comments
- Required keys: `OPENAI_API_KEY`, `ALPHA_VANTAGE_KEY`, `FINNHUB_KEY`, `GNEWS_KEY`, `ANGEL_ONE_API_KEY`, `ANGEL_ONE_CLIENT_CODE`
- Optional keys: `SERPER_API_KEY`, `LANGSMITH_API_KEY`, `DATA_GOV_IN_KEY`
- Set up Python virtual environment with `pyproject.toml` (use `uv` or `poetry`)
- Set up Next.js with TypeScript strict mode, Tailwind, shadcn/ui

**Task 0.3 — Docker Compose baseline**
- Write `docker-compose.yml` with all 5 services (mcp-server, frontend, keycloak, redis, postgres)
- Ensure `docker compose up` works with empty/stub services
- Add health check endpoints for each service
- Volume mounts for Keycloak realm import and Postgres data persistence

**Task 0.4 — LangSmith tracing setup**
- Integrate LangSmith for all LLM calls (CrewAI and direct OpenAI)
- Every tool invocation, every agent thought, every API call should be traceable
- Set up project in LangSmith dashboard with tags per use case (ps1, ps2, ps3)
- This is non-negotiable — without tracing, debugging CrewAI is impossible

---

### Phase 1: Auth layer (Day 1-2, ~8 hours)

This is 25% of the evaluation score. Build it first, build it right.

**Task 1.1 — Keycloak realm configuration**
- Create realm `finint` with three client roles: `free`, `premium`, `analyst`
- Create OAuth 2.1 client with PKCE enabled (public client, no client secret)
- Define all scopes from the spec: `market:read`, `fundamentals:read`, `technicals:read`, `mf:read`, `news:read`, `filings:read`, `filings:deep`, `macro:read`, `macro:historical`, `research:generate`, `watchlist:read`, `watchlist:write`, `portfolio:read`, `portfolio:write`
- Map scopes to tiers:
  - `free` → `market:read`, `mf:read`, `news:read`, `watchlist:read`, `watchlist:write`
  - `premium` → all free + `fundamentals:read`, `technicals:read`, `macro:read`, `portfolio:read`, `portfolio:write`
  - `analyst` → all premium + `filings:read`, `filings:deep`, `macro:historical`, `research:generate`
- Create 3 test users: `free_user`, `premium_user`, `analyst_user`
- Export realm as JSON for reproducible Docker setup

**Task 1.2 — Protected Resource Metadata endpoint**
- Implement `GET /.well-known/oauth-protected-resource` on the MCP server
- Must return JSON with `authorization_servers` array and `scopes_supported`
- This is how MCP clients discover where to authenticate (RFC 9728)

**Task 1.3 — Token validation middleware**
- Implement middleware that runs before every MCP tool/resource call
- Fetch Keycloak JWKS (JSON Web Key Set) and cache it
- Validate: signature (RS256), expiry (`exp` claim), audience (`aud` claim per RFC 8707), issuer
- Extract scopes from token claims
- On missing/invalid token: return `401` with `WWW-Authenticate` header containing `resource_metadata` URL
- On insufficient scopes: return `403` with `insufficient_scope` error

**Task 1.4 — Tier-aware tool discovery**
- When MCP client connects and calls `tools/list`, filter the tool list based on the user's tier
- Free users should NOT see `cross_reference_signals`, `generate_research_brief`, etc.
- Premium users see more tools but not the analyst-only ones
- This is "capability negotiation" in MCP spec terms

**Task 1.5 — Rate limiter**
- Implement sliding window rate limiter in Redis
- Key: `rate:{user_id}:{window}`, TTL = window duration
- Limits: Free 30/hour, Premium 150/hour, Analyst 500/hour
- On limit exceeded: return `429` with `Retry-After` header (seconds until next window)
- Also track upstream API quotas (Alpha Vantage 25/day, GNews 100/day) separately

**Task 1.6 — Audit logging**
- Log every tool invocation: `{user_id, tier, tool_name, timestamp, latency_ms, cache_hit, source_used}`
- Store in PostgreSQL `audit_log` table
- This is explicitly required in the rubric under "System Design & Technical Depth"

---

### Phase 2: Data facade + adapters (Day 2-3, ~10 hours)

**Task 2.1 — ISIN normalizer / symbol mapper**
- Build a mapping table: NSE symbol ↔ BSE scrip code ↔ ISIN ↔ yfinance ticker ↔ Alpha Vantage ticker
- Pre-populate for Nifty 50 + Nifty Next 50 (100 stocks covers 90% of demo needs)
- Every adapter receives ISIN and translates to its own symbol format
- Store mapping in PostgreSQL, load into memory at startup

**Task 2.2 — Cache layer**
- Implement dual-layer cache: L1 (Python `cachetools.LRUCache`, 1000 entries) + L2 (Redis)
- TTL configuration per data type (defined in `config/ttl.py`):
  - Quotes: 30s during market hours (9:15-15:30 IST), 12h after
  - Fundamentals: 24h
  - News: 15min
  - MF NAV: 12h
  - Filings: permanent (immutable data)
  - Macro (RBI rates): 7 days
- Implement stale-while-revalidate: serve stale data immediately, refresh in background
- Add TTL jitter (±10%) to prevent cache stampede

**Task 2.3 — Circuit breaker**
- Implement per-source circuit breaker with three states: CLOSED (normal), OPEN (failing, skip), HALF-OPEN (testing recovery)
- Configuration: failure threshold = 5 failures in 60s → OPEN for 60s → HALF-OPEN (try 1 request)
- When circuit is OPEN, immediately fall to next source in chain without waiting

**Task 2.4 — Data source adapters (one per source, assign to different team members)**

**Task 2.4a — Angel One SmartAPI adapter**
- Real-time quotes via REST, historical OHLCV, WebSocket for live streaming
- Handle TOTP-based authentication flow
- Map Angel One instrument tokens to ISINs
- Note: From April 2026, static IP is mandatory — document this requirement
- Priority: P0 (primary source for all price data)

**Task 2.4b — MFapi.in adapter**
- Scheme search, latest NAV, historical NAV
- No auth required — simplest adapter
- Map scheme codes to fund names, fund houses, categories
- Priority: P0 (sole source for MF data)

**Task 2.4c — BSE India adapter**
- Corporate announcements, quarterly results, shareholding patterns, corporate actions
- Reverse-engineer BSE website endpoints (use `BseIndiaApi` Python package as reference)
- Handle pagination for announcement lists
- For filing PDFs: download and store in temp storage, pass to LLM-based parser
- Priority: P0 (sole source for filings and results)

**Task 2.4d — Finnhub adapter**
- Company news, earnings calendar, recommendations
- 60 req/min free tier — generous but track usage
- India coverage is partial — use primarily for news and earnings calendar
- Priority: P1

**Task 2.4e — Alpha Vantage adapter**
- Technical indicators (RSI, MACD, SMA, EMA, Bollinger Bands)
- Fundamentals (income statement, balance sheet, cash flow)
- Only 25 req/day — implement aggressive caching and request prioritization
- Use `.BSE` ticker suffix for Indian stocks
- Priority: P1

**Task 2.4f — RBI DBIE adapter**
- No REST API exists — build a scraper/downloader for key datasets
- Pre-fetch and store: repo rate, CPI, WPI, GDP, forex reserves, USD/INR
- Update via scheduled job (daily at 6 AM IST)
- Alternatively: hardcode current values for hackathon, build proper ingestion for production
- Priority: P2

**Task 2.4g — GNews adapter**
- Indian financial news with search and filtering
- 100 req/day free tier
- Use as fallback/supplement to Finnhub for Indian-specific news
- Priority: P2

**Task 2.4h — yfinance adapter**
- Historical prices, financial statements, balance sheets
- UNRELIABLE — use only as fallback, never as primary
- Implement aggressive retry with exponential backoff
- Use `yfinance-cache` package to minimize requests
- Priority: P3 (fallback only)

**Task 2.5 — Fallback chain configuration**
- Define source priority chains per data type:
  - Price data: Angel One → yfinance → stale cache
  - Fundamentals: Alpha Vantage → yfinance → stale cache
  - News: Finnhub → GNews → stale cache
  - MF data: MFapi.in (no fallback — single authoritative source)
  - Filings: BSE India (no fallback — single authoritative source)
  - Macro: RBI DBIE pre-fetched data → data.gov.in → hardcoded values

---

### Phase 3: MCP tools implementation (Day 3-5, ~16 hours)

Every tool must follow these standards:
- Return structured JSON, never narrative text
- Include `source` field with API name and timestamp
- Include `cache_status` field (hit/miss/stale)
- Include `disclaimer` field on any analytical output
- Use Pydantic models for input validation and output schema
- Handle errors gracefully — return `{error: "...", fallback_data: {...}}` not exceptions

**Task 3.1 — Shared market data tools (used by all 3 use cases)**

| Tool | Input | Output | Data source |
|---|---|---|---|
| `get_stock_quote` | `symbol: str` | LTP, change, volume, market cap, P/E, 52W range | Angel One → yfinance |
| `get_price_history` | `symbol, from_date, to_date, interval` | OHLCV array with pagination | Angel One → yfinance |
| `get_index_data` | `index: str` (NIFTY50, SENSEX, etc.) | Value, change, composition stocks | Angel One |
| `get_top_gainers_losers` | `exchange: str, count: int` | Sorted arrays of gainers and losers | Angel One |
| `get_technical_indicators` | `symbol, indicators: list` | RSI, MACD, SMA, EMA values | Alpha Vantage |
| `get_company_news` | `symbol, days: int` | Array of news articles with titles, sources, URLs | Finnhub → GNews |
| `get_news_sentiment` | `symbol, days: int` | Aggregated score -1 to +1, article count, driver type | Finnhub + FinBERT |
| `get_market_news` | `category: str` | Broad market / sector news | GNews |
| `search_mutual_funds` | `query: str` | Array of matching scheme codes, names, categories | MFapi.in |
| `get_fund_nav` | `scheme_code: int` | Latest NAV, historical NAV array | MFapi.in |
| `get_rbi_rates` | none | Repo rate, reverse repo, CRR, SLR with dates | RBI DBIE (pre-fetched) |
| `get_inflation_data` | `months: int` | CPI and WPI time series | RBI DBIE (pre-fetched) |

**Task 3.2 — PS1 specific tools (Financial Research Copilot)**

| Tool | Input | Output | Tier |
|---|---|---|---|
| `get_financial_statements` | `symbol, statement_type, period` | Income/balance/cashflow data | Premium |
| `get_key_ratios` | `symbol` | P/E, P/B, ROE, ROCE, debt/equity, etc. | Premium |
| `get_shareholding_pattern` | `symbol, quarters: int` | Promoter, FII, DII, retail % over time | Premium |
| `get_quarterly_results` | `symbol` | Latest quarterly with YoY/QoQ comparison | Premium |
| `compare_funds` | `scheme_codes: list` | Side-by-side NAV, returns, category comparison | Premium |
| `get_corporate_filings` | `symbol, filing_type` | List of recent filings with metadata | Premium |
| `cross_reference_signals` | `symbol` | Multi-source signal matrix with contradictions | Analyst |
| `generate_research_brief` | `symbol` | Full research note with citations per source | Analyst |
| `compare_companies` | `symbols: list` | Side-by-side comparison across all dimensions | Analyst |

**Task 3.3 — PS2 specific tools (Portfolio Risk Monitor)**

| Tool | Input | Output | Tier |
|---|---|---|---|
| `add_to_portfolio` | `symbol, quantity, avg_price` | Confirmation + updated portfolio | Free |
| `remove_from_portfolio` | `symbol` | Confirmation + updated portfolio | Free |
| `get_portfolio_summary` | none (user-scoped) | Current value, P&L, allocation breakdown | Free |
| `portfolio_health_check` | none | Concentration risk flags, sector exposure | Premium |
| `check_concentration_risk` | none | Flags if any stock >20% or sector >40% | Premium |
| `check_mf_overlap` | none | Overlap between holdings and top MF schemes | Premium |
| `check_macro_sensitivity` | none | Holdings sensitivity to rate/inflation/forex | Premium |
| `detect_sentiment_shift` | none | 7-day vs 30-day sentiment comparison per holding | Premium |
| `portfolio_risk_report` | none | Full cross-source risk narrative with citations | Analyst |
| `what_if_analysis` | `scenario: str` | Portfolio impact simulation | Analyst |

**Task 3.4 — PS3 specific tools (Earnings Command Center)**

| Tool | Input | Output | Tier |
|---|---|---|---|
| `get_earnings_calendar` | `weeks: int` | Upcoming results dates, Nifty 50/500 | Free |
| `get_past_results_dates` | `symbol` | Historical announcement dates | Free |
| `get_eps_history` | `symbol, quarters: int` | EPS time series with YoY/QoQ trend | Premium |
| `get_pre_earnings_profile` | `symbol` | Last 4Q results + ratios + shareholding + options + sentiment | Premium |
| `get_analyst_expectations` | `symbol` | Consensus estimates (or extrapolated estimate) | Premium |
| `get_post_results_reaction` | `symbol, filing_date` | Price change on result day + next 2 days, volume spike | Premium |
| `compare_actual_vs_expected` | `symbol` | Beat/miss/inline verdict with magnitude | Premium |
| `get_filing_document` | `symbol, filing_id` | Raw filing PDF/HTML content | Analyst |
| `parse_quarterly_filing` | `symbol, filing_id` | LLM-extracted revenue, PAT, EPS, margins | Analyst |
| `earnings_verdict` | `symbol` | Full cross-source narrative: results + reaction + why | Analyst |
| `earnings_season_dashboard` | `week_date` | Who beat, who missed, sector trends | Analyst |
| `compare_quarterly_performance` | `symbols: list` | Same-quarter side-by-side for 2-4 companies | Analyst |
| `get_option_chain` | `symbol, expiry` | Full option chain with OI, Greeks | Premium |

---

### Phase 4: MCP resources and prompts (Day 4-5, ~6 hours)

**Task 4.1 — Resources (read-only contextual data)**

| Resource URI | Description | Update frequency |
|---|---|---|
| `market://overview` | Nifty, Sensex, Bank Nifty, top movers, FII/DII flows | 60s during market hours |
| `macro://snapshot` | Repo rate, CPI, GDP, forex reserves, USD/INR | Daily |
| `watchlist://{user_id}/stocks` | User's personal watchlist | On write |
| `research://{ticker}/latest` | Most recent cached research brief | On generation |
| `portfolio://{user_id}/holdings` | User's portfolio (PS2) | On write |
| `portfolio://{user_id}/alerts` | Active risk alerts (PS2) | On health check |
| `portfolio://{user_id}/risk_score` | Overall portfolio risk score (PS2) | On health check |
| `earnings://calendar/upcoming` | Next 2 weeks of earnings dates (PS3) | Daily |
| `earnings://{ticker}/latest` | Most recent parsed quarterly result (PS3) | On parse |
| `earnings://{ticker}/history` | Last 8 quarters of structured data (PS3) | Quarterly |
| `filing://{ticker}/{filing_id}` | Parsed BSE filing content (PS3) | Permanent |

**Task 4.2 — Resource subscriptions (bonus, but critical for PS2)**
- Implement pub/sub via Redis for `portfolio://{user_id}/alerts`
- When a health check detects a new risk signal, publish to the subscription
- MCP clients that subscribed get notified in real-time

**Task 4.3 — Prompt templates**

| Prompt | Use case | Arguments | Tier |
|---|---|---|---|
| `quick_analysis` | PS1 | `symbol` | Free |
| `deep_dive` | PS1 | `symbol` | Premium |
| `sector_scan` | PS1 | `sector` | Premium |
| `morning_brief` | PS1 | none | Premium |
| `morning_risk_brief` | PS2 | none | Premium |
| `rebalance_suggestions` | PS2 | none | Premium |
| `earnings_exposure` | PS2 | none | Premium |
| `earnings_preview` | PS3 | `symbol` | Premium |
| `results_flash` | PS3 | `symbol` | Premium |
| `sector_earnings_recap` | PS3 | `sector` | Analyst |
| `earnings_surprise_scan` | PS3 | none | Analyst |

---

### Phase 5: CrewAI agent crews (Day 5-6, ~10 hours)

**Task 5.1 — Research crew (PS1)**

5 agents, sequential process:
1. **Data Collector** (GPT-4o-mini, temp 0) — fetches price, volume, delivery data from Angel One + BSE
2. **Fundamental Analyst** (GPT-4o, temp 0.3) — analyzes ratios, financials from Alpha Vantage + yfinance
3. **Sentiment Analyst** (GPT-4o-mini, temp 0.2) — scores news from Finnhub + GNews
4. **Macro Analyst** (GPT-4o, temp 0.3) — maps RBI data to sector/stock impact
5. **Synthesizer** (GPT-4o, temp 0.5) — combines all signals, detects contradictions, outputs `CrossSourceAnalysis` Pydantic model

Output model (Pydantic, enforced):
- `signals: List[Signal]` — each with source, direction (-1 to +1), confidence, evidence
- `contradictions: List[str]` — explicitly listed
- `synthesis: str` — narrative paragraph
- `overall_confidence: float` — 0.0 to 1.0
- `citations: List[Citation]` — source name, data point, timestamp per claim

**Task 5.2 — Risk crew (PS2)**

4 agents, sequential process:
1. **Portfolio Scanner** (GPT-4o-mini) — fetches current prices for all holdings, calculates P&L
2. **Risk Detector** (GPT-4o) — checks concentration, sector tilt, compares to thresholds
3. **Macro Mapper** (GPT-4o) — maps macro indicators to portfolio-specific impact
4. **Risk Narrator** (GPT-4o, temp 0.5) — produces `PortfolioRiskReport` Pydantic model

**Task 5.3 — Earnings crew (PS3)**

4 agents, sequential process:
1. **Filing Fetcher** (GPT-4o-mini) — gets BSE filing, downloads PDF
2. **Filing Parser** (GPT-4o) — LLM-based extraction of revenue, PAT, EPS, margins
3. **Market Reactor** (GPT-4o-mini) — fetches price reaction on result day + 2 days
4. **Earnings Narrator** (GPT-4o, temp 0.5) — produces `EarningsVerdict` Pydantic model

**Task 5.4 — Custom CrewAI tools**
- Each data facade adapter is also wrapped as a CrewAI `BaseTool`
- Agents use these tools within their task execution
- Tools must return JSON strings (CrewAI limitation — agents parse the JSON)
- Each tool must include `source` and `timestamp` in its output

---

### Phase 6: Frontend dashboard (Day 5-7, ~12 hours)

**Task 6.1 — Auth integration**
- Integrate `keycloak-js` adapter in Next.js
- On app load: check for valid token → if not, redirect to Keycloak login
- Store token in memory (not localStorage — security best practice)
- Display current user tier in header
- "Upgrade tier" button that switches to a different Keycloak user for demo

**Task 6.2 — MCP client integration**
- Use `@modelcontextprotocol/sdk` TypeScript package to connect to MCP server
- Pass Bearer token with every MCP request
- Handle 401 (re-auth), 403 (show upgrade prompt), 429 (show retry countdown)
- Display tool discovery results (show which tools the user's tier can access)

**Task 6.3 — Tab 1: Research Copilot (PS1)**
- Search bar: type a stock symbol → calls `get_stock_quote` + `get_company_news`
- Quick analysis card: calls `quick_analysis` prompt
- Deep dive button (Premium+): triggers full `deep_dive` prompt
- Cross-source panel (Analyst): shows signal matrix with confirms/contradicts
- Research brief display: formatted markdown with source citations
- Company comparison: select 2-5 stocks → `compare_companies`

**Task 6.4 — Tab 2: Portfolio Monitor (PS2)**
- Portfolio builder: add stocks with quantity and price → `add_to_portfolio`
- Portfolio summary card: current value, P&L, allocation pie chart
- Health check button (Premium+): runs all risk detection tools, displays alerts
- Risk report panel (Analyst): full cross-source narrative
- What-if simulator (Analyst): dropdown for scenarios ("RBI cuts 25bps", "USD/INR +5%")
- Alert feed: real-time alerts from resource subscriptions

**Task 6.5 — Tab 3: Earnings Center (PS3)**
- Earnings calendar view: upcoming results dates in a timeline/grid
- Pre-earnings card: select company → `get_pre_earnings_profile` → display preview
- Post-earnings card: after results → `results_flash` → show beat/miss verdict
- Earnings verdict panel (Analyst): full cross-source narrative
- Sector recap (Analyst): aggregated earnings season dashboard
- Company comparison: side-by-side quarterly performance

**Task 6.6 — Settings / Status page**
- User tier display with scope list
- Upstream API status dashboard (health check endpoint)
- Rate limit usage meter (calls remaining this hour)
- Cache statistics (hit rate, entries)

---

### Phase 7: Demo preparation (Day 7-8, ~6 hours)

**Task 7.1 — Demo script for each use case**

**PS1 demo (5 minutes):**
1. Free user logs in → searches "HDFC Bank" → gets quote + news → tries `get_financial_statements` → sees 403 error with clear "upgrade to Premium" message
2. Switch to Premium user → runs `quick_analysis` for INFY → gets quote + ratios + news + shareholding in one card
3. Switch to Analyst → runs `deep_dive` for RELIANCE → system pulls from 5+ sources → shows full research brief with per-source citations → brief saved to `research://RELIANCE/latest`
4. Show `cross_reference_signals` for TCS → highlight contradictions (price down but fundamentals strong)

**PS2 demo (5 minutes):**
1. Add 5 stocks to portfolio (HDFC Bank, TCS, Infosys, Reliance, DLF)
2. Run `portfolio_health_check` → shows 38% IT sector concentration flag
3. Run `check_mf_overlap` → "HDFC Bank and ICICI Bank are in 7 of top 10 large-cap MF schemes"
4. Run `portfolio_risk_report` (Analyst) → full cross-source narrative combining NSE + RBI + Finnhub + MFapi
5. Run `what_if_analysis` for "RBI cuts rates 25bps" → shows banking stocks gain, real estate gains more

**PS3 demo (5 minutes):**
1. Show `earnings_calendar` → upcoming results dates
2. Pre-earnings: `earnings_preview` for INFY → EPS history + shareholding + options + sentiment
3. Post-earnings: `results_flash` for a company that has reported → parse filing → beat/miss verdict
4. `earnings_verdict` (Analyst) → full narrative: results + price reaction + shareholding + "why" explanation
5. `compare_quarterly_performance` for TCS vs INFY → side-by-side comparison

**Task 7.2 — Must-show auth boundary (required by rubric)**
- Script a clear moment where: Free user → 403 → Premium user → success → Analyst tool → 403 → Analyst user → success
- Make this visually obvious in the frontend (error cards, upgrade prompts)

**Task 7.3 — Must-show cross-source moment (required by rubric)**
- In each tab, ensure the cross-source tool explicitly lists which APIs confirmed vs contradicted
- Example output: "Price: ₹2,456 [Angel One] | Quarterly revenue: +15% YoY [BSE Filing #12345] | FII holding: +2.1% [BSE shareholding] | News sentiment: -0.3 [Finnhub, 12 articles] | Contradiction: positive fundamentals but negative sentiment — driven by sector-wide US recession fears, not company-specific"

**Task 7.4 — Client compatibility demo**
- Show MCP server working with Claude Desktop (connect via Streamable HTTP)
- Show same server working in VS Code (MCP extension)
- Show same server in Windsurf
- All three clients discover the same tools, respect the same auth boundaries

---

### Phase 8: Documentation and polish (Day 8, ~4 hours)

**Task 8.1 — README.md**
- One-command setup: `docker compose up`
- List of required API keys with signup links
- Troubleshooting section
- Screenshots of each tab

**Task 8.2 — Architecture diagram**
- Use the diagrams we created (high-level, CrewAI engine, OAuth flow, data facade)
- Export as images and embed in `docs/architecture.md`

**Task 8.3 — API documentation**
- Complete reference of all tools (input schemas, output schemas, required scopes)
- Resource URI patterns with examples
- Prompt templates with argument descriptions
- Error response examples (401, 403, 429)

**Task 8.4 — Technical explanation document**
- MCP primitive design decisions (what's a tool vs resource vs prompt and why)
- OAuth 2.1 implementation details
- CrewAI cross-source reasoning architecture
- Caching strategy with TTL rationale
- Security: API key isolation, audit logging, no financial advice guardrails

---

## Engineering standards (non-negotiable)

### Python (MCP server)
- **Type annotations everywhere** — use `mypy --strict`
- **Pydantic models** for all tool inputs and outputs — no raw dicts
- **Async/await** throughout — every adapter, every cache call, every DB query
- **Docstrings** on every public function (Google style) — CrewAI agents read these
- **No hardcoded secrets** — everything from environment variables
- **Structured logging** — use `structlog` with JSON output, include `user_id`, `tool_name`, `latency_ms`
- **Error handling** — never crash, always return structured error JSON with fallback data
- **Constants file** — all TTL values, rate limits, thresholds in one place (`config/constants.py`)

### TypeScript (Frontend)
- **Strict mode** — `"strict": true` in `tsconfig.json`
- **No `any` types** — define interfaces for every MCP response
- **Server components by default** — only use `"use client"` where interactivity is needed
- **shadcn/ui** for all UI components — no custom CSS for standard elements
- **Error boundaries** — wrap each tab in an error boundary with graceful fallback
- **Loading states** — skeleton UI for every async operation
- **Responsive** — must work on mobile (judges may test on phone)

### Git workflow
- Feature branches: `feat/auth-middleware`, `feat/angel-one-adapter`, etc.
- PR required for merge to `develop`
- At least one approval per PR (pair review)
- Commit messages: conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`)
- No force push to `develop` or `main`

### Testing
- Unit tests for every adapter (mock the HTTP calls)
- Unit tests for cache layer (mock Redis)
- Integration test for auth flow (Keycloak test container)
- Smoke test: `docker compose up` → health check all endpoints → run one tool per use case
- CrewAI testing: use `crewai test --n_iterations 2` to verify crew execution

---

## Timeline summary

| Day | Phase | Key deliverable |
|---|---|---|
| Day 1 | Setup + Auth | Docker Compose running, Keycloak configured, auth middleware working |
| Day 2 | Auth + Adapters | Full OAuth flow end-to-end, Angel One + MFapi.in adapters |
| Day 3 | Adapters + Tools | All 8 adapters, cache layer, circuit breakers, 12 shared tools |
| Day 4 | Tools + Resources | PS1/PS2/PS3 specific tools, resources, prompts |
| Day 5 | CrewAI + Frontend start | 3 CrewAI crews working, frontend auth + tab structure |
| Day 6 | Frontend | All 3 tabs functional, MCP client connected |
| Day 7 | Integration + Demo prep | End-to-end flow working, demo scripts rehearsed |
| Day 8 | Polish + Docs | Documentation complete, final testing, submission |

---

## Risk mitigation

| Risk | Mitigation |
|---|---|
| Angel One API requires static IP from April 2026 | Use for data reads only (not trading). If blocked, fall to yfinance |
| yfinance rate-limited/blocked | It's already our P3 fallback, not primary. Serve stale cache on failure |
| Alpha Vantage 25 req/day exhausted | Aggressive 24h caching. Pre-warm cache for demo stocks before presentation |
| BSE endpoint changes mid-hackathon | Hardcode sample BSE data for 5 demo stocks as emergency fallback |
| CrewAI agents hallucinate financial numbers | System prompt: "NEVER fabricate numbers. ALL claims must come from tool outputs." Pydantic validation catches schema violations |
| Keycloak setup takes too long | Prepare realm JSON export in advance. Single import command |
| LLM API costs spiral during development | Use GPT-4o-mini for all development/testing. Switch to GPT-4o only for demo |
| Frontend ↔ MCP connection issues | Build a CLI test harness first. Frontend is the visual layer on top of a working backend |

---

## Final checklist before submission

- [ ] `docker compose up` starts all services in under 2 minutes
- [ ] Three test users (free/premium/analyst) can log in via Keycloak
- [ ] Free user sees limited tools, hits 403 on premium tools
- [ ] Premium user sees more tools, hits 403 on analyst tools
- [ ] Analyst user sees all tools including cross-source reasoning
- [ ] Rate limiting returns 429 with Retry-After header
- [ ] `cross_reference_signals` combines 3+ APIs with explicit confirm/contradict
- [ ] `portfolio_risk_report` combines NSE + RBI + Finnhub + MFapi
- [ ] `earnings_verdict` combines BSE filing + NSE price + shareholding + sentiment
- [ ] All tool outputs include `source` field with API name and timestamp
- [ ] All cross-source outputs include `disclaimer` field
- [ ] LangSmith shows full trace of every agent call
- [ ] Works with Claude Desktop (Streamable HTTP)
- [ ] Works with VS Code or Windsurf
- [ ] README has setup instructions and API key signup links
- [ ] Architecture diagram submitted
- [ ] API documentation complete
