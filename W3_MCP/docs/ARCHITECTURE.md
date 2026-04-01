# Architecture — Indian Financial Intelligence (W3 MCP)

FastMCP server + Next.js UI + Keycloak + Postgres + Redis. Structured JSON tools, tiered OAuth, multi-source data via **DataFacade**, analyst synthesis via **CrewAI**.

| Doc | Role |
|-----|------|
| [DEPLOYMENT.md](DEPLOYMENT.md) | Runbooks |
| [MCP.md](MCP.md) | **MCP & HTTP clients only:** `/mcp`, REST bridge, IDE setup, curl — not system design |

---

## Contents

[System & data flow](#system--data-flow) · [Routes](#routes) · [Auth & enforcement](#auth--enforcement) · [Data facade & adapters](#data-facade--adapters) · [Cache & limits](#cache--limits) · [CrewAI](#crewai) · [**Cross-source trust score (special feature)**](#cross-source-trust-score-special-feature) · [Persistence](#persistence) · [Frontend & observability](#frontend--observability) · [Repo layout](#repo-layout) · [Requirements traceability](#requirements-traceability) · [Summary](#summary) · [Appendix: REST tool sequence](#appendix-rest-tool-call-sequence)

---

## Goals & scope

- **Product:** One MCP surface over Indian equities, MF, news, filings, macro; **Free / Premium / Analyst** tiers; cross-source reasoning on analyst tier. A **special differentiator** on analyst cross-source tools is the deterministic **trust score** layer (agreement, contradictions, missing signals)—see [Cross-source trust score](#cross-source-trust-score-special-feature).
- **Technical:** Upstream keys only on server; tools return JSON (`source`, disclaimers); **Docker Compose** for demo.
- **Use cases:** PS1 Research (`cross_source`, `research_crew`) · PS2 Portfolio (`portfolio`, `risk_crew`) · PS3 Earnings (`earnings`, `earnings_crew`) (repo implements all three product tracks).

---

## System & data flow

```mermaid
flowchart TB
  subgraph c["Clients"]
    WEB[Browser :10005]
    CLI[MCP POST /mcp + Bearer]
  end
  subgraph d["Docker Compose"]
    FE[frontend]
    MS[mcp-server]
    PG[(postgres)]
    RD[(redis)]
    KC[keycloak]
  end
  WEB --> FE
  CLI --> MS
  FE --> KC
  FE -->|REST + Bearer| MS
  MS --> PG & RD
  MS -->|JWKS| KC
  MS --> EXT[Angel One, AV, Finnhub, GNews, BSE, MFapi, RBI, yfinance, OpenAI]
```

| Unit | Role |
|------|------|
| **frontend** | Next.js, NextAuth → Keycloak; calls MCP **REST bridge** |
| **mcp-server** | FastMCP: `/mcp`, `/api/tool/*`, `/api/resource`, health, OAuth metadata |
| **postgres** | Portfolios, audit, ISIN map, caches, tier requests (schema) |
| **redis** | L2 cache + per-user rate windows |
| **keycloak** | Realm `finint`, roles `free` / `premium` / `analyst` |

**Internals (`mcp-server/src`):** `server.py` (ASGI, CORS, routes) → `auth/` (JWT via `provider.py`, **`mcp_keycloak.py`** `KeycloakMCPVerifier` + **`finint_component_auth`** / FastMCP `AuthMiddleware` on `/mcp`, `TOOL_SCOPE_MAP`, `TierToolFilter` for REST, rate limit, audit) → `tools/*`, `resources/`, `prompts/` → `data_facade/` (cache, breakers, `adapters/*`) → `crews/` + `models/`. Analyst cross-source responses are post-processed by **`cross_source/`** (trust envelope); see [below](#cross-source-trust-score-special-feature).

---

## Routes

| | Path | Auth |
|---|------|------|
| Public | `/health`, `/api/status`, `/.well-known/oauth-protected-resource` | — |
| Bridge | `POST /api/tool/{name}`, `GET /api/resource?uri=` | Bearer JWT |
| Other | `POST /api/tier-request`, admin tier routes | JWT (admin for `/api/admin/*`) |
| MCP | `POST /mcp` | See [enforcement table](#authorization-enforcement-surfaces) |

Tools load via `_register_tools()` importing `tools.*`, `resources.resources`, `prompts.prompts`.

**Wiring MCP or curl to these routes:** [MCP.md](MCP.md).

---

## Auth & enforcement

- **Flow:** User → Keycloak (NextAuth + **PKCE**) → JWT on `Authorization: Bearer` to MCP REST calls.
- **JWT (`auth/provider.py`):** JWKS (cached), RS256, issuer, audience, `exp`.
- **Scopes:** From **`realm_access.roles` → highest tier → `TIER_SCOPES[tier]`** in `config/constants.py` (not the JWT `scope` string as primary).
- **Gating:** `TOOL_SCOPE_MAP` maps each tool → one required scope **or** a tuple of scopes (**all** must be present, e.g. `compare_funds` → `mf:read` + `fundamentals:read` for PDF Premium+). REST bridge uses `TierToolFilter.is_tool_allowed()` / `tool_scope_specs()`. Native **`POST /mcp`** uses the same tier-derived scopes via **`KeycloakMCPVerifier`** and **`AuthMiddleware(auth=finint_component_auth)`**, which filters **tools, prompts, and resources** by scope (prompt/resource rules in `mcp_keycloak.py`).

### Authorization enforcement surfaces

| Surface | JWT | Scope | Rate limit | Audit |
|---------|-----|-------|------------|-------|
| `POST /api/tool/{name}` | ✓ | ✓ (`TOOL_SCOPE_MAP`, multi-scope AND) | Redis | Postgres (best-effort) |
| `GET /api/resource?uri=` | ✓ | Not `TOOL_SCOPE_MAP` (bridge does not re-check URI scopes) | — | — |
| `POST /mcp` | ✓ (`KeycloakMCPVerifier`) | ✓ (`AuthMiddleware` + `finint_component_auth`: tools / prompts / resources) | — | — |

**Note:** REST resource bridge still authenticates JWT only; **tier-aware resource access** is enforced on the native MCP path. Prefer **`GET /api/resource`** from the dashboard only for trusted UI paths, or extend the bridge with URI→scope checks later.

**Implication:** Dashboard REST and native MCP both require a **valid Bearer JWT**; **`tools/list`**, **prompts**, and **resources** lists on `/mcp` reflect the caller’s tier scopes (PDF capability negotiation).

---

## Data facade & adapters

**`DataFacade`:** L1+L2 read → on miss, **fallback chain** per data type (circuit breaker per adapter) → write-through with TTL → **stale** read if all fail → structured error.

**`isin_mapper`:** Symbol / ISIN / provider tickers.

| File | Role |
|------|------|
| `angel_one.py` | Quotes (session auth) |
| `alpha_vantage.py` | Fundamentals, technicals |
| `finnhub.py` | News, calendar |
| `gnews.py` | News backup |
| `bse.py` | Filings / announcements |
| `mfapi.py` | MF NAV, search |
| `rbi_dbie.py` | Macro |
| `yfinance_adapter.py` | Fallback |

---

## Cache & limits

**TTLs** (full constants in `config/constants.py`): quotes ~**30s** (session), **24h** fundamentals, **~15m** news, **7d** macro/shareholding, filings long-lived; **± jitter**.

**Circuit breaker:** Per adapter in `DataFacade._breakers` (thresholds in `constants.py`).

**User limits:** 30 / 150 / 500 calls/hour by tier, Redis sliding window, **429** + `Retry-After`. **Upstream daily** caps (e.g. Alpha Vantage, GNews): `rate_limiter.py` (`_UPSTREAM_DAILY_LIMITS`).

---

## CrewAI

Cross-source tools run **`research_crew`**, **`risk_crew`**, **`earnings_crew`** (sequential processes, OpenAI, Pydantic outputs: signals, citations, contradictions, disclaimer). **`tracing.py`** → LangSmith when configured.

---

## Cross-source trust score (special feature)

This is an **intentional product edge**, not generic API aggregation: selected analyst tools attach a **deterministic** (no LLM scoring) envelope so clients can show **confidence**, **signal agreement vs contradiction**, and **structured conflicts** across sources.

| | |
|--|--|
| **Rationale** | Deterministic agreement / contradiction scoring over normalized multi-source signals (no LLM score). |
| **Code** | `mcp-server/src/cross_source/` — `signal_normalizer.py`, `conflict_detector.py`, `trust_scorer.py`; entry `compute_trust_envelope()` |
| **Merged into `data`** | `trust_score`, `signal_summary`, `conflicts`, `evidence_matrix`, `trust_score_reasoning` |
| **Tools** | `cross_reference_signals`, `generate_research_brief`, `earnings_verdict`, `portfolio_risk_report` |
| **UI** | `frontend/components/trust-score-panel.tsx` on Research, Earnings verdict, Portfolio risk report |

CrewAI may still produce narratives and signal rows; the trust layer **re-scores in pure Python** from normalized signals plus cross-topic rules (e.g. price vs sentiment, earnings vs price reaction). Heuristic fallbacks use the same path; portfolio heuristic supplies **synthetic signal rows** so the engine stays unified.

---

## Persistence

**Tables:** `users`, `portfolios`, `watchlists`, `audit_log`, `isin_mapping`, `macro_data`, `cached_research`, `tier_upgrade_requests`.

**Drift:** Some MCP resources still use **in-memory** watchlist/research in `resources.py`; Postgres schema exists for alignment.

---

## Frontend & observability

- **Next.js App Router:** `research`, `portfolio`, `earnings`, `settings`, `admin`, etc. **`lib/mcp-client.ts`** → REST bridge + Bearer from NextAuth session. Analyst views surface the **trust score panel** when tool `data` includes trust fields ([special feature](#cross-source-trust-score-special-feature)).
- **CORS:** Permissive (`*`) for demo; `Mcp-Session-Id` exposed.
- **Logs / health / audit / LLM:** `structlog`, `/health`, `/api/status`, `audit_log`, LangSmith.

---

## Repo layout

```
W3_MCP/
├── mcp-server/src/   server.py, auth/ (provider, middleware, **mcp_keycloak**, …), config/, data_facade/, cross_source/, tools/, resources/, prompts/, crews/, models/
├── frontend/
├── keycloak/, db/, docker-compose.yml, .env.example
└── docs/             this file, DEPLOYMENT, MCP
```

---

## Requirements traceability

Implementation checklist versus the original product spec (auth, data sources, tiers, MCP compliance).

### Data & auth

| Topic | Status | Note |
|-------|--------|------|
| ≥4 APIs, ≥3 data types | Met | 8 adapters |
| NSE-style example | Partial | Angel One + yfinance |
| data.gov.in | Gap | — |
| OAuth 2.1 + PKCE | Met | NextAuth + Keycloak |
| RFC 9728 metadata | Met | `/.well-known/oauth-protected-resource` |
| JWT validate (sig, exp, aud) | Met | JWKS |
| 401/403 discovery headers | Met | REST: `WWW-Authenticate` includes `resource_metadata` from `settings.oauth_resource_metadata_url`; 403 adds `insufficient_scope` + `scope` hint and JSON `required_scopes` (list). MCP transport errors follow FastMCP auth behavior. |
| Tiers 30/150/500 | Met | Redis |
| IdP separate from MCP | Met | |
| Keys server-side only | Met | |

### Technical & product

| Topic | Status | Note |
|-------|--------|------|
| Streamable HTTP + Docker | Met | |
| Tier-aware `tools/list` | Met | FastMCP `AuthMiddleware` + `finint_component_auth`; `TierToolFilter.filter_tools` still available for non-MCP consumers |
| Pagination | Partial | caps/`days`, not uniform offset |
| Resource subscriptions | Gap | PS2 bonus |
| Structured errors / facade degrade | Partial | |
| Cache policy | Met | ~30s quotes, etc. |
| User store for watchlist/research | Partial | in-memory + schema |
| Audit | Met | |
| Citations / JSON / disclaimers | Met | |
| `macro:historical` depth | Partial | scopes vs tools |
| PS1 | Met | |
| PS2 | Partial | No MCP resource **subscriptions** (polling only); `/mcp` tier matrix aligned for tools/prompts/resources; REST `/api/resource` is JWT-only without per-URI scope matrix |
| PS3 | Met | |
| Deliverables (README, compose, diagrams) | Met | OpenAPI for all tools: Partial |

**Tier matrix (implementation notes):** PS2-style matrix: `portfolio_health_check` / `check_concentration_risk` are **Premium+** (`portfolio:read`); code matches. **`compare_funds`** requires **`mf:read` and `fundamentals:read`** (AND), so comparison stays **Premium+**.

---

## Summary

Stack: **Keycloak** + **FastMCP** (REST bridge + **`/mcp` with JWT + tier-aware lists** via `KeycloakMCPVerifier` / `AuthMiddleware`) + **Redis/Postgres** + **DataFacade** + **CrewAI** + **`cross_source` trust envelope** on analyst cross-source tools ([special feature](#cross-source-trust-score-special-feature)).

**Hardening:** Resource **subscriptions** (MCP notify); REST **URI→scope** checks for `/api/resource` if desired; persist watchlist/research resources; **pagination** uniformity; optional **data.gov.in** adapter.

---

## Appendix: REST tool call sequence

```mermaid
sequenceDiagram
  participant C as Client
  participant R as /api/tool/{name}
  participant J as JWT validate
  participant F as TierToolFilter
  participant W as RateLimiter
  participant T as call_tool
  C->>R: POST + Bearer
  R->>J: validate
  J-->>C: 401 if invalid
  R->>F: allowed?
  F-->>C: 403 if not
  R->>W: limit?
  W-->>C: 429 if over
  R->>T: execute
  T-->>C: JSON
```
