# Indian Financial Intelligence — MCP Server

Production-grade MCP (Model Context Protocol) server that unifies **8 Indian financial data sources** into a single intelligence layer with **OAuth 2.1 tiered access**, **cross-source AI reasoning via CrewAI**, and a **Next.js 14 dashboard**. Implements three complete use cases: Research Copilot (PS1), Portfolio Risk Monitor (PS2), and Earnings Season Command Center (PS3).

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                      Next.js 14 Dashboard (:10005)                   │
│  ┌───────────────┐  ┌────────────────┐  ┌─────────────────────────┐ │
│  │ PS1 Research   │  │ PS2 Portfolio  │  │ PS3 Earnings Command    │ │
│  │ Copilot        │  │ Risk Monitor   │  │ Center                  │ │
│  └───────┬───────┘  └───────┬────────┘  └────────────┬────────────┘ │
│          └──────────────────┼────────────────────────┘              │
│                   NextAuth.js + Keycloak OIDC                       │
└─────────────────────────────┬───────────────────────────────────────┘
                              │ REST / MCP Streamable HTTP
┌─────────────────────────────▼───────────────────────────────────────┐
│                FastMCP Server — Python 3.12 (:10004)                 │
│                                                                      │
│  ┌─────────┐  ┌─────────────┐  ┌───────────┐  ┌──────────────────┐ │
│  │  Auth    │  │  44 Tools   │  │ 11 Rsrc   │  │  11 Prompts      │ │
│  │  Layer   │  │  (tiered)   │  │           │  │                  │ │
│  └────┬────┘  └──────┬──────┘  └─────┬─────┘  └────────┬─────────┘ │
│       │       ┌──────▼────────────────▼─────────────────▼────────┐  │
│       │       │          Data Aggregation Facade                 │  │
│       │       │   L1 LRU (1000) · L2 Redis · Circuit Breakers   │  │
│       │       │   ISIN Normalization · Fallback Chains           │  │
│       │       └──┬──────┬──────┬──────┬──────┬──────┬────────────┘  │
│       │          │      │      │      │      │      │               │
│  ┌────▼───┐ ┌───▼──┐┌──▼──┐┌──▼──┐┌──▼──┐┌──▼──┐┌──▼───────┐      │
│  │Keycloak│ │Angel ││MFapi││BSE  ││Finn ││Alpha││yfinance  │      │
│  │  JWT   │ │ One  ││ .in ││India││hub  ││Vant.││(fallback)│      │
│  └────────┘ └──────┘└─────┘└─────┘└─────┘└─────┘└──────────┘      │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │       CrewAI Multi-Agent Reasoning Engine                │      │
│  │   Research Crew (5 agents) · Risk Crew (4) · Earnings (4)│      │
│  │   GPT-4o reasoning · GPT-4o-mini collection              │      │
│  │   LangSmith tracing · Pydantic output validation         │      │
│  └──────────────────────────────────────────────────────────┘      │
└──────────────────────────────────────────────────────────────────────┘
        ┌───────────┐     ┌───────────┐     ┌───────────┐
        │PostgreSQL │     │  Redis 7  │     │ Keycloak  │
        │   16      │     │  (cache)  │     │  24.x     │
        │  :10001   │     │  :10002   │     │  :10003   │
        └───────────┘     └───────────┘     └───────────┘
```

### Six-Layer Architecture

| Layer | Responsibility | Technology |
|-------|---------------|------------|
| **1. MCP Clients** | Claude Desktop, VS Code, Windsurf, custom apps | MCP Streamable HTTP |
| **2. API Gateway + Auth** | OAuth 2.1 PKCE, rate limiting, audit logging, tier enforcement | Keycloak 24.x + JWT |
| **3. MCP Server Core** | Tool/Resource/Prompt registry, scope enforcement, REST bridge | FastMCP (Python 3.12) |
| **4. Intelligence Layer** | Multi-agent cross-source reasoning with structured output | CrewAI + GPT-4o + Pydantic |
| **5. Data Facade** | Adapter pattern, circuit breakers, fallback chains, caching | Redis 7 + LRU L1 |
| **6. External Sources** | 8 financial data APIs for Indian markets | Angel One, BSE, Finnhub, etc. |

---

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env — OPENAI_API_KEY is required for CrewAI agents

# 2. Build and launch all 5 services
docker compose build --no-cache && docker compose up -d

# 3. Verify health
curl http://localhost:10004/health        # MCP Server
open http://localhost:10005               # Dashboard
open http://localhost:10003               # Keycloak admin (admin/admin)
```

### Host Port Map

| Port | Service | Internal | Notes |
|------|---------|----------|-------|
| **10001** | PostgreSQL | 5432 | Schema + Nifty 50 ISIN seed |
| **10002** | Redis | 6379 | 128MB LRU cache |
| **10003** | Keycloak | 8080 | OAuth 2.1 + PKCE, admin/admin |
| **10004** | MCP Server | 10004 | FastMCP + REST bridge |
| **10005** | Dashboard | 10005 | Next.js 14 + Tailwind |

### Environment Variables (.env)

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | **Yes** | GPT-4o for CrewAI reasoning |
| `ALPHA_VANTAGE_KEY` | Recommended | Fundamentals + technicals (25/day) |
| `FINNHUB_KEY` | Recommended | News + earnings calendar (60/min) |
| `GNEWS_KEY` | Optional | Indian news search (100/day) |
| `ANGEL_ONE_API_KEY` | Optional | Real-time quotes from SmartAPI |
| `ANGEL_ONE_API_SECRET` | Optional | SmartAPI secret key |
| `ANGEL_ONE_CLIENT_CODE` | Optional | Trading client ID |
| `ANGEL_ONE_PASSWORD` | Optional | Account PIN |
| `ANGEL_ONE_TOTP_SECRET` | Optional | TOTP seed for 2FA |
| `LANGSMITH_API_KEY` | Optional | LangSmith tracing |

---

## Three Use Cases

### PS1: Research Copilot — *"Tell me everything about Reliance"*

Full-stack research with cross-source AI analysis. Free users get quotes and news; Premium adds fundamentals, technicals, shareholding; Analyst gets multi-source signal matrix with contradiction detection.

**Tools (15):** `get_stock_quote`, `get_price_history`, `get_index_data`, `get_top_gainers_losers`, `get_key_ratios`, `get_financial_statements`, `get_shareholding_pattern`, `get_quarterly_results`, `get_technical_indicators`, `get_company_news`, `get_market_news`, `get_news_sentiment`, `compare_companies`, `cross_reference_signals`, `generate_research_brief`

**CrewAI Research Crew (5 agents):**
1. **Market Data Collector** (GPT-4o-mini) — fetches price, volume, technicals
2. **Fundamental Analyst** (GPT-4o) — evaluates ratios vs sector averages
3. **Sentiment Analyst** (GPT-4o-mini) — scores news sentiment, classifies drivers
4. **Macro Analyst** (GPT-4o) — assesses RBI rates, CPI, sector impact
5. **Synthesizer** (GPT-4o) — combines signals, detects contradictions, assigns confidence

### PS2: Portfolio Risk Monitor — *"The risk detection war room"*

Real-time portfolio tracking with concentration alerts, MF overlap detection, macro sensitivity, and what-if scenarios. Holdings persisted in PostgreSQL.

**Tools (11):** `add_to_portfolio`, `remove_from_portfolio`, `get_portfolio_summary`, `portfolio_health_check`, `check_concentration_risk`, `check_mf_overlap`, `check_macro_sensitivity`, `detect_sentiment_shift`, `portfolio_risk_report`, `what_if_analysis`

**CrewAI Risk Crew (4 agents):**
1. **Price Scanner** — scans current prices for all holdings
2. **Risk Detector** — identifies concentration, sector tilt, volatility
3. **Macro Mapper** — maps RBI rate/CPI impact to portfolio sectors
4. **Narrative Generator** — produces structured risk report with citations

### PS3: Earnings Season Command Center — *"The results season war room"*

Tracks earnings calendar, builds pre-earnings profiles (last 4Q EPS + options activity + FII trend + sentiment), parses post-earnings filings, cross-references market reaction with actual numbers.

**Tools (13):** `get_earnings_calendar`, `get_past_results_dates`, `get_eps_history`, `get_pre_earnings_profile`, `get_analyst_expectations`, `get_post_results_reaction`, `compare_actual_vs_expected`, `get_option_chain`, `earnings_verdict`, `earnings_season_dashboard`, `compare_quarterly_performance`, `get_filing_document`, `parse_quarterly_filing`

**CrewAI Earnings Crew (4 agents):**
1. **Filing Fetcher** (GPT-4o-mini) — retrieves BSE quarterly filings
2. **Filing Parser** (GPT-4o) — extracts revenue, PAT, EPS, margins via LLM
3. **Market Reactor** (GPT-4o-mini) — analyzes price reaction + news sentiment
4. **Earnings Narrator** (GPT-4o) — synthesizes verdict with contradictions + citations

**Supporting Tools (shared):** `get_rbi_rates`, `get_inflation_data`, `search_mutual_funds`, `get_fund_nav`, `compare_funds`, `get_corporate_filings`

---

## Tiered Access Control (OAuth 2.1 + PKCE)

### Scope Architecture

| Scope | Tier | Description |
|-------|------|-------------|
| `market:read` | Free | Quotes, indices, gainers/losers |
| `mf:read` | Free | MF search, NAV lookup |
| `news:read` | Free | Company/market news |
| `watchlist:read/write` | Free | Portfolio add/remove, summary, health check |
| `fundamentals:read` | Premium | Ratios, financials, shareholding, EPS history |
| `technicals:read` | Premium | RSI, SMA, MACD indicators |
| `macro:read` | Premium | RBI rates, inflation, GDP |
| `portfolio:read` | Premium | MF overlap, macro sensitivity, sentiment shift |
| `filings:read` | Premium | Corporate filing listings |
| `filings:deep` | Analyst | Raw filing documents, LLM-parsed quarterly results |
| `research:generate` | Analyst | Cross-source signals, research briefs, risk reports, earnings verdicts |

### PS1 Tier Matrix

| Tool | Free | Premium | Analyst |
|------|:----:|:-------:|:-------:|
| `get_stock_quote`, `get_price_history`, `get_index_data` | ✅ | ✅ | ✅ |
| `get_company_news`, `get_market_news` | ✅ | ✅ | ✅ |
| `search_mutual_funds`, `get_fund_nav` | ✅ | ✅ | ✅ |
| `get_key_ratios`, `get_financial_statements`, `get_shareholding_pattern` | ❌ | ✅ | ✅ |
| `get_technical_indicators`, `get_news_sentiment` | ❌ | ✅ | ✅ |
| `cross_reference_signals`, `generate_research_brief` | ❌ | ❌ | ✅ |

### PS2 Tier Matrix

| Tool | Free | Premium | Analyst |
|------|:----:|:-------:|:-------:|
| `add_to_portfolio`, `remove_from_portfolio`, `get_portfolio_summary` | ✅ | ✅ | ✅ |
| `portfolio_health_check`, `check_concentration_risk` | ✅ | ✅ | ✅ |
| `check_mf_overlap`, `check_macro_sensitivity`, `detect_sentiment_shift` | ❌ | ✅ | ✅ |
| `portfolio_risk_report`, `what_if_analysis` | ❌ | ❌ | ✅ |

### PS3 Tier Matrix

| Tool | Free | Premium | Analyst |
|------|:----:|:-------:|:-------:|
| `get_earnings_calendar`, `get_past_results_dates` | ✅ | ✅ | ✅ |
| `get_eps_history`, `get_pre_earnings_profile`, `get_analyst_expectations` | ❌ | ✅ | ✅ |
| `get_post_results_reaction`, `compare_actual_vs_expected`, `get_option_chain` | ❌ | ✅ | ✅ |
| `get_filing_document`, `parse_quarterly_filing` | ❌ | ❌ | ✅ |
| `earnings_verdict`, `earnings_season_dashboard`, `compare_quarterly_performance` | ❌ | ❌ | ✅ |

### Rate Limits

| Tier | Calls/Hour | Enforcement |
|------|-----------|-------------|
| Free | 30 | Redis sliding window, `429 Retry-After` |
| Premium | 150 | Redis sliding window |
| Analyst | 500 | Redis sliding window |

### Demo Users (Keycloak)

| Username | Password | Tier | Scopes |
|----------|----------|------|--------|
| `free_user` | `free123` | Free | market, mf, news, watchlist |
| `premium_user` | `premium123` | Premium | + fundamentals, technicals, macro, portfolio, filings |
| `analyst_user` | `analyst123` | Analyst | All scopes |
| `admin` | `admin123` | Admin | All scopes + admin endpoints |

---

## MCP Compliance

### Transport & Protocol

- **Streamable HTTP** at `POST /mcp` — full MCP protocol support
- **REST Bridge** at `POST /api/tool/{name}` and `GET /api/resource?uri=...` — for non-MCP clients
- **Session Management** via `Mcp-Session-Id` header
- **Capability Negotiation** — server advertises tools, resources, prompts

### OAuth 2.1 Discovery

```
GET /.well-known/oauth-protected-resource
→ {
    "resource": "http://localhost:10004",
    "authorization_servers": ["http://localhost:10003/realms/finint"],
    "scopes_supported": ["market:read", "fundamentals:read", ...],
    "bearer_methods_supported": ["header"]
  }
```

### Primitives

| Type | Count | Examples |
|------|-------|---------|
| **Tools** | 44 | `get_stock_quote`, `earnings_verdict`, `portfolio_risk_report` |
| **Resources** | 11 | `market://overview`, `earnings://{ticker}/latest`, `portfolio://{user_id}/holdings` |
| **Prompts** | 11 | `quick_analysis`, `deep_dive`, `earnings_preview`, `results_flash` |

### MCP Resources (11)

| URI | Description |
|-----|-------------|
| `market://overview` | Nifty 50 + Sensex live values |
| `macro://snapshot` | Repo rate, CPI, GDP, forex, USD/INR |
| `watchlist://{user_id}/stocks` | User's watchlist |
| `research://{ticker}/latest` | Cached research brief |
| `portfolio://{user_id}/holdings` | Portfolio holdings |
| `portfolio://{user_id}/alerts` | Active risk alerts |
| `portfolio://{user_id}/risk_score` | Overall risk score |
| `earnings://calendar/upcoming` | Next 2 weeks of earnings dates |
| `earnings://{ticker}/latest` | Most recent parsed quarterly result |
| `earnings://{ticker}/history` | Last 8 quarters of structured data |
| `filing://{ticker}/{filing_id}` | Parsed BSE filing content |

### MCP Prompts (11)

| Prompt | Tier | Description |
|--------|------|-------------|
| `quick_analysis` | Free | Quote + news summary |
| `deep_dive` | Premium | 8-step comprehensive analysis |
| `sector_scan` | Premium | Compare all major stocks in a sector |
| `morning_brief` | Premium | Morning market summary |
| `morning_risk_brief` | Premium | Portfolio risk overview |
| `rebalance_suggestions` | Premium | Concentration + overlap analysis |
| `earnings_exposure` | Premium | Portfolio earnings calendar overlap |
| `earnings_preview` | Premium | Pre-results: EPS trend + estimates + sentiment |
| `results_flash` | Premium | Post-results: beat/miss + market reaction |
| `sector_earnings_recap` | Analyst | Aggregate sector earnings performance |
| `earnings_surprise_scan` | Analyst | Biggest positive/negative surprises |

---

## Data Sources

| Source | Type | Rate Limit | Used For | Fallback |
|--------|------|-----------|----------|----------|
| **Angel One SmartAPI** | Real-time quotes, OHLCV | High | Primary price feed | yfinance |
| **Alpha Vantage** | Fundamentals, technicals | 25/day | Key ratios, RSI/SMA/MACD | yfinance |
| **Finnhub** | News, earnings calendar | 60/min | Company/market news, sentiment | GNews |
| **GNews** | Indian news search | 100/day | Backup news source | — |
| **BSE India** | Filings, results | Moderate | Corporate announcements, quarterly results | — |
| **MFapi.in** | Mutual fund NAV | None | Fund search, NAV, comparison | — |
| **RBI DBIE** | Macro data | Pre-fetched | Repo rate, CPI, GDP, forex reserves | — |
| **yfinance** | Fallback everything | Throttled | Quotes, fundamentals, options, quarterly earnings | — |

### Fallback Chains

```
Price:        Angel One → yfinance → stale cache
Fundamentals: Alpha Vantage → yfinance → stale cache
News:         Finnhub → GNews
MF:           MFapi.in (no fallback needed — very reliable)
Filings:      BSE India
Macro:        RBI DBIE (pre-fetched, 7-day TTL)
Options:      yfinance (NSE .NS suffix)
Quarterly EPS: yfinance (ticker.quarterly_earnings)
```

### Cache Strategy

| Data Type | TTL | Layer |
|-----------|-----|-------|
| Quotes (market hours) | 30s | L1 + L2 |
| Quotes (after hours) | 12h | L2 |
| Fundamentals | 24h | L2 |
| News | 15min | L2 |
| MF NAV | 12h | L2 |
| Filings | Permanent | L2 |
| Macro (RBI) | 7 days | L2 |
| Technicals | 6h | L2 |
| Shareholding | 7 days | L2 |
| Earnings | 24h | L2 |

All TTLs include ±10% jitter to prevent cache stampede.

---

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| MCP Server | Python + FastMCP | 3.12 |
| Auth Server | Keycloak (OAuth 2.1 + PKCE) | 24.x |
| Frontend | Next.js + TypeScript + Tailwind + shadcn/ui | 14 |
| LLM | OpenAI API | GPT-4o + GPT-4o-mini |
| AI Agents | CrewAI (13 agents across 3 crews) | Latest |
| Tracing | LangSmith (OpenTelemetry + OpenInference) | — |
| Cache | Redis (dual-layer with in-memory L1) | 7 Alpine |
| Database | PostgreSQL (portfolios, audit, ISIN map) | 16 Alpine |
| Deployment | Docker Compose (5 services) | — |

---

## Project Structure

```
W3_MCP/
├── mcp-server/                        # Python MCP server
│   ├── src/
│   │   ├── auth/                      # JWT validation, scopes, rate limiting, audit
│   │   │   ├── middleware.py          # TOOL_SCOPE_MAP, TierToolFilter
│   │   │   ├── provider.py           # KeycloakAuthProvider, TokenClaims
│   │   │   ├── rate_limiter.py       # Redis sliding window rate limiter
│   │   │   └── audit.py              # PostgreSQL audit logger
│   │   ├── config/
│   │   │   ├── settings.py           # Pydantic settings from env
│   │   │   └── constants.py          # TTLs, rate limits, scopes, tier definitions
│   │   ├── crews/                     # CrewAI multi-agent pipelines
│   │   │   ├── research_crew.py      # 5-agent research analysis
│   │   │   ├── risk_crew.py          # 4-agent portfolio risk
│   │   │   └── earnings_crew.py      # 4-agent earnings analysis
│   │   ├── data_facade/
│   │   │   ├── facade.py             # DataFacade: cache → fallback chain → stale
│   │   │   ├── cache.py              # L1 LRU + L2 Redis dual-layer
│   │   │   ├── circuit_breaker.py    # Per-adapter failure tracking + recovery
│   │   │   ├── isin_mapper.py        # Symbol → ISIN normalization
│   │   │   └── adapters/             # 8 data source adapters
│   │   │       ├── angel_one.py      # Real-time quotes (TOTP auth)
│   │   │       ├── alpha_vantage.py  # Fundamentals + technicals
│   │   │       ├── finnhub_adapter.py # News + earnings calendar
│   │   │       ├── bse_adapter.py    # Filings + corporate actions
│   │   │       ├── mfapi_adapter.py  # Mutual fund NAV + search
│   │   │       ├── rbi_adapter.py    # Macro data (repo, CPI, GDP)
│   │   │       ├── gnews_adapter.py  # Indian news backup
│   │   │       └── yfinance_adapter.py # Universal fallback
│   │   ├── tools/                     # 44 MCP tools organized by domain
│   │   │   ├── market/tools.py       # Quotes, history, indices, gainers
│   │   │   ├── fundamentals/tools.py # Ratios, financials, shareholding
│   │   │   ├── news/tools.py         # News, sentiment
│   │   │   ├── macro/tools.py        # RBI rates, inflation
│   │   │   ├── mf/tools.py           # MF search, NAV, compare
│   │   │   ├── portfolio/tools.py    # PS2: 11 portfolio tools
│   │   │   ├── earnings/tools.py     # PS3: 13 earnings tools
│   │   │   ├── filings/tools.py      # Filing document + parse
│   │   │   └── cross_source/tools.py # Cross-reference + research brief
│   │   ├── resources/resources.py     # 11 MCP resources
│   │   ├── prompts/prompts.py         # 11 MCP prompt templates
│   │   └── server.py                  # FastMCP entry + REST bridge + auth middleware
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                          # Next.js 14 dashboard
│   ├── app/
│   │   ├── research/page.tsx          # PS1: Research Copilot UI
│   │   ├── portfolio/page.tsx         # PS2: Portfolio Monitor UI
│   │   ├── earnings/page.tsx          # PS3: Earnings Command Center UI
│   │   ├── settings/page.tsx          # Account + server status + tier upgrade
│   │   └── admin/page.tsx             # Tier request management
│   ├── components/
│   │   ├── navbar.tsx                 # Navigation with tier badge
│   │   └── providers.tsx              # NextAuth session provider
│   └── lib/
│       ├── auth.ts                    # Keycloak OIDC config
│       ├── mcp-client.ts             # callMCPTool() — REST bridge client
│       └── utils.ts                   # cn(), tierBadge()
├── keycloak/
│   └── realm-export.json              # Finint realm: roles + test users
├── db/
│   └── init.sql                       # Schema: portfolios, audit_log, isin_map
├── docker-compose.yml                 # 5 services, health checks, networks
├── .env.example                       # Template for API keys
└── docs/
    ├── architecture-doc.md            # Detailed 6-layer architecture
    └── task-breakdown.md              # Implementation task list
```

---

## API Endpoints

Base URL: `http://localhost:10004`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | None | Health check + version |
| `GET` | `/.well-known/oauth-protected-resource` | None | RFC 9728 OAuth discovery |
| `GET` | `/api/status` | None | Upstream API health status |
| `POST` | `/mcp` | Bearer JWT | MCP Streamable HTTP endpoint |
| `POST` | `/api/tool/{name}` | Bearer JWT | REST bridge — invoke any MCP tool |
| `GET` | `/api/resource?uri=...` | Bearer JWT | REST bridge — read any MCP resource |
| `POST` | `/api/tier-request` | Bearer JWT | Submit tier upgrade request |
| `GET` | `/api/admin/tier-requests` | Admin JWT | List all pending tier requests |
| `POST` | `/api/admin/tier-requests/{id}/approve` | Admin JWT | Approve a tier upgrade |
| `POST` | `/api/admin/tier-requests/{id}/reject` | Admin JWT | Reject a tier upgrade |

### REST Bridge Usage

```bash
# Get a stock quote (Free tier)
curl -X POST http://localhost:10004/api/tool/get_stock_quote \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "RELIANCE"}'

# Run cross-source analysis (Analyst tier)
curl -X POST http://localhost:10004/api/tool/cross_reference_signals \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "TCS"}'

# Read a resource
curl "http://localhost:10004/api/resource?uri=market://overview" \
  -H "Authorization: Bearer $TOKEN"
```

---

## Demo Scripts

### Demo 1: Auth Boundary Moment

```
1. Sign in as free_user (free123)
2. Go to Earnings → Load Calendar → works ✅
3. Enter "INFY" → click "EPS History" → 403 "Premium tier required" ❌
4. Go to Settings → Request upgrade to Analyst
5. Sign in as admin (admin123) → Admin tab → Approve
6. Sign back as analyst_user (analyst123)
7. Enter "INFY" → click "EPS History" → 8 quarters of data ✅
8. Click "Run Earnings Verdict" → full cross-source narrative ✅
```

### Demo 2: PS1 Cross-Source Reasoning

```
1. Sign in as analyst_user
2. Research tab → Search "TCS"
3. Quote: ₹3,450 (+1.2%) [Angel One]
4. News: "TCS wins $500M deal" [Finnhub]
5. Click "Run Analysis" →
   Signal 1: [price] momentum = +0.65 (conf: 82%) [Angel One]
   Signal 2: [news] sentiment = +0.80 (conf: 75%) [Finnhub]
   Signal 3: [fundamental] direction = +0.60 (conf: 70%) [Alpha Vantage]
   Signal 4: [macro] RBI impact = -0.20 (conf: 60%) [RBI DBIE]
   Contradiction: "Positive sentiment but IT sector facing margin pressure"
6. Overall Confidence: 72%, 4 citations from 4 sources
```

### Demo 3: PS2 Portfolio Risk Monitor

```
1. Sign in as analyst_user → Portfolio tab
2. Add holdings: TCS (50 @ ₹3200), HDFCBANK (100 @ ₹1500), RELIANCE (30 @ ₹2400)
3. Click "Health Check" →
   Risk Score: 75/100
   Alert: TCS is 50.7% of portfolio (threshold: 20%) [HIGH]
   Alert: HDFCBANK is 32.1% (threshold: 20%) [HIGH]
4. Click "MF Overlap" → 3 of 4 holdings in top large-cap MF schemes
5. Click "What-If: RBI cuts 25bps" → banking sector impact analysis
```

### Demo 4: PS3 Earnings Season Command Center

```
1. Sign in as analyst_user → Earnings tab
2. Load Calendar → upcoming earnings dates
3. Enter "INFY" → click "Pre-Earnings Profile" →
   Last 4Q EPS with YoY/QoQ trends
   Key ratios: P/E 18.1, ROE 42.6%
   FII Trend: decreasing (-1.8pp)
   Options PCR: 0.85, Max Pain: ₹1,420
   News Sentiment: +0.15 (neutral-positive)
4. Click "Run Earnings Verdict" →
   "INFY reported EPS of ₹16.43 vs estimated ₹15.90 (beat, +3.3% surprise) [yfinance].
    Stock fell 3.1% on results day [NSE]. FII holding decreased 1.8pp in prior
    quarter [shareholding data]. News sentiment: neutral (+0.15) from 5 articles [Finnhub]."
   Contradiction: "Earnings beat but stock fell — sell-off may be pre-positioned or guidance-driven."
   Citations: [yfinance] EPS ₹16.43, [NSE] Price ₹1,420 (-3.1%), [shareholding] FII -1.8pp, [Finnhub] Sentiment +0.15
5. Click "Season Dashboard" → 10 companies: 6 beats, 2 misses, 2 inline
6. Enter "TCS,INFY,WIPRO" → Compare → side-by-side: EPS, revenue, P/E, ROE, FII change, price reaction
```

### Demo 5: Must-Show Cross-Source Moment (PS3)

The `earnings_verdict` tool combines data from **5 independent sources** into a single narrative:

| Source | Data Point | Citation Format |
|--------|-----------|-----------------|
| **yfinance** | Quarterly EPS (₹16.43) | `[yfinance] EPS ₹16.43` |
| **NSE (Angel One)** | Price reaction (-3.1%) | `[NSE] Price ₹1,420 (-3.1%)` |
| **BSE (shareholding)** | FII change (-1.8pp) | `[shareholding] FII change -1.8pp` |
| **Finnhub** | News sentiment (+0.15) | `[Finnhub] Sentiment +0.15 from 5 articles` |
| **Historical EPS** | Expected EPS (₹15.90) | `[yfinance_extrapolated] Growth rate 8.2%` |

The verdict detects contradictions: if earnings beat but stock falls, it identifies the disconnect as potentially "pre-positioned" or "guidance-driven."

---

## Cross-Source Reasoning Quality

Every cross-source tool follows this pattern:

1. **Multi-API Data Collection** — pulls from 3-5 independent sources
2. **Signal Extraction** — each source produces a directional signal with confidence
3. **Contradiction Detection** — explicitly flags when sources disagree
4. **Evidence Citation** — every claim cites `[Source Name]: specific data point`
5. **Structured Output** — Pydantic-validated JSON (signals, contradictions, narrative, citations)

### Example: `cross_reference_signals("TCS")`

```json
{
  "data": {
    "symbol": "TCS",
    "signals": [
      {"source": "Angel One", "signal_type": "price", "direction": 0.5, "confidence": 0.8,
       "evidence": "LTP ₹2,389.80 (+1.2% today)"},
      {"source": "Alpha Vantage", "signal_type": "fundamental", "direction": 0.6, "confidence": 0.7,
       "evidence": "ROE: 42.6%, P/E: 18.1"},
      {"source": "Finnhub", "signal_type": "sentiment", "direction": 0.3, "confidence": 0.6,
       "evidence": "Sentiment: +0.30 from 8 articles"},
      {"source": "RBI DBIE", "signal_type": "macro", "direction": 0.0, "confidence": 0.5,
       "evidence": "Repo rate: 6.5%, CPI: 4.2%"}
    ],
    "contradictions": ["Positive sentiment but IT sector facing margin pressure"],
    "overall_confidence": 0.65,
    "citations": [...]
  }
}
```

---

## Authentication Flow

```
User → Dashboard → Keycloak Login (PKCE)
     → JWT with tier-based scopes
     → Dashboard sends Bearer token to MCP Server
     → middleware.py: validate JWT → check TOOL_SCOPE_MAP → rate limit → audit log
     → Tool executes → structured JSON response
```

### Auth Enforcement Chain

1. **JWT Validation** — Keycloak JWKS endpoint, issuer/audience check
2. **Scope Check** — `TOOL_SCOPE_MAP[tool_name]` mapped to user's JWT scopes
3. **Rate Limiting** — Redis sliding window per user_id per tier
4. **Audit Logging** — PostgreSQL log: user, tool, tier, timestamp, result
5. **Tier-Aware Discovery** — `tools/list` only returns tools user can access

### Error Responses

| Code | Header | Meaning |
|------|--------|---------|
| `401` | `WWW-Authenticate: Bearer` | Missing or invalid token |
| `403` | `WWW-Authenticate: Bearer scope="..."` | Insufficient tier/scope |
| `429` | `Retry-After: N` | Rate limit exceeded |

---

## Development

### Rebuild After Code Changes

```bash
# Rebuild specific service
docker compose up -d --build mcp-server
docker compose up -d --build frontend

# Rebuild all
docker compose up -d --build

# Clear Redis cache
docker compose exec redis redis-cli FLUSHDB

# View MCP server logs
docker compose logs -f mcp-server

# Check service health
curl http://localhost:10004/health
curl http://localhost:10004/api/status
```

### Running Tests

```bash
# Get tokens for testing
FREE_TOKEN=$(curl -s -X POST "http://localhost:10003/realms/finint/protocol/openid-connect/token" \
  -d "grant_type=password&client_id=finint-dashboard&username=free_user&password=free123" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

ANALYST_TOKEN=$(curl -s -X POST "http://localhost:10003/realms/finint/protocol/openid-connect/token" \
  -d "grant_type=password&client_id=finint-dashboard&username=analyst_user&password=analyst123" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Test tier boundary: Free → 403 on analyst tool
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:10004/api/tool/earnings_verdict \
  -H "Authorization: Bearer $FREE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"INFY"}'
# Expected: 403

# Test analyst access
curl -s -X POST http://localhost:10004/api/tool/get_eps_history \
  -H "Authorization: Bearer $ANALYST_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"TCS","quarters":8}' | python3 -m json.tool
```

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| CrewAI process | Sequential (not hierarchical) | Predictable, debuggable, 4 LLM calls vs 8-10 |
| LLM per agent | GPT-4o-mini (collection) + GPT-4o (reasoning) | 10x cost difference; collection doesn't need reasoning |
| Cache layers | L1 in-memory LRU + L2 Redis | 97%+ hit rate, <5ms for hot data |
| Auth server | Keycloak (separate container) | MCP spec requires separate auth server |
| Estimates | Historical EPS extrapolation | Free-tier API coverage for Indian stocks is limited |
| Options data | yfinance NSE (.NS) | No free real-time NSE option chain API available |
| Filing parsing | LLM-based extraction | BSE PDFs have inconsistent formats across companies |
| Output format | Pydantic-validated JSON | MCP spec: tools return structured data, client handles narrative |
| Fallback strategy | Adapter chain + stale cache | Graceful degradation when upstream APIs fail |
