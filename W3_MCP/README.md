# Indian Financial Intelligence — MCP Server

**FinInt (W3 MCP)** is a production-oriented stack that exposes Indian equities, mutual funds, news, filings, and macro indicators as **tiered MCP tools, resources, and prompts**, secured with **OAuth 2.1 (Keycloak)** and consumed by a **Next.js** dashboard and standard MCP clients.

Three product tracks are implemented end-to-end:

| Track | Focus | Typical entry points |
|-------|--------|----------------------|
| **PS1 — Research Copilot** | Cross-source stock research | `cross_reference_signals`, `generate_research_brief`, Research UI |
| **PS2 — Portfolio risk** | Holdings, concentration, macro sensitivity | `portfolio_health_check`, `portfolio_risk_report`, Portfolio UI |
| **PS3 — Earnings season** | Results, calendar, verdict | `get_earnings_calendar`, `earnings_verdict`, Earnings UI |

**CrewAI** powers analyst-grade multi-agent synthesis; a **deterministic trust-score layer** (`cross_source/`) augments selected tools so the UI can show agreement, conflicts, and confidence without LLM-based scoring.

---

## Documentation map

| Document | Audience | Contents |
|----------|----------|----------|
| **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** | Everyone | Deep-dive: layers, E2E lifecycle, CrewAI (agents/tasks/crew/tools/memory/planning), tools design, communication & API flow, LLM strategy, **QA playbook**, observability, appendices |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | DevOps / SRE | Docker, EC2, ports, build args, public URLs |
| [docs/MCP.md](docs/MCP.md) | Client integrators | `/mcp`, REST bridge, IDE setup, curl examples |
| [docs/data-sources-guide.md](docs/data-sources-guide.md) | Data / backend | External APIs, keys, fallbacks |

### Reading guide by role

- **New developer:** Start with [System architecture (deep dive)](docs/ARCHITECTURE.md#1-system-architecture-deep-dive) and [Tools architecture](docs/ARCHITECTURE.md#3-tools-architecture), then skim `mcp-server/src/server.py` and `data_facade/facade.py`.
- **QA engineer:** Use [Testing & validation](docs/ARCHITECTURE.md#7-testing--validation-qa-perspective) and [Sample execution report](docs/ARCHITECTURE.md#sample-execution-report).
- **AI/ML engineer:** Read [CrewAI concepts](docs/ARCHITECTURE.md#2-crewai-concepts-detailed-explanation) and [LLM & prompt engineering](docs/ARCHITECTURE.md#6-llm--prompt-engineering); inspect `mcp-server/src/crews/*.py` and `tracing.py`.
- **System architect:** Focus on [Communication flow](docs/ARCHITECTURE.md#4-communication-flow), [API & data flow](docs/ARCHITECTURE.md#5-api--data-flow), persistence, and [Requirements traceability](docs/ARCHITECTURE.md#requirements-traceability).

**Deliverables** requested for this documentation pass are consolidated as follows:

| Deliverable | Location |
|-------------|----------|
| Enhanced architecture | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) (full rewrite / expansion) |
| Enhanced README | This file |
| QA report & strategy | [§7 Testing & validation](docs/ARCHITECTURE.md#7-testing--validation-qa-perspective) |
| Execution flow documentation | [§1.3 E2E lifecycle](docs/ARCHITECTURE.md#13-end-to-end-request-lifecycle-dashboard--tool--data), [§4 Communication flow](docs/ARCHITECTURE.md#4-communication-flow), [Appendix A](docs/ARCHITECTURE.md#appendix-a--rest-tool-call-sequence-detailed) |

---

## Repository layout (high level)

```
W3_MCP/
├── mcp-server/          # Python FastMCP: tools, resources, prompts, JWT, rate limits, audit, DataFacade, CrewAI, DB repos
├── frontend/            # Next.js App Router: research / portfolio / earnings / brief / alerts / settings / admin
├── keycloak/            # Realm export (tiers, clients, demo users)
├── db/                  # PostgreSQL init (schema seed)
├── docker-compose.yml   # Orchestrates services
├── .env.example         # Required and optional keys (commented)
└── docs/                # ARCHITECTURE, DEPLOYMENT, MCP, data-sources-guide
```

Detailed tree: [docs/ARCHITECTURE.md — Appendix C](docs/ARCHITECTURE.md#appendix-c--repo-layout).

---

## Run locally

From the directory that contains `docker-compose.yml`:

```bash
cd W3_MCP

cp .env.example .env
# Set OPENAI_API_KEY (required for CrewAI). Add other keys as needed — see .env.example.

docker compose up -d --build
```

First startup may take **1–2 minutes** (Keycloak realm import, health checks).

| URL | Service |
|-----|---------|
| http://localhost:10005 | Dashboard (Next.js) |
| http://localhost:10004 | MCP server (`/health`, `POST /mcp`, `POST /api/tool/...`) |
| http://localhost:10003 | Keycloak |

**Verify**

```bash
curl -s http://localhost:10004/health
```

**Cloud or custom hostnames** (build args, `OAUTH_RESOURCE_URL`, security groups): [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

---

## Configuration

| Variable | Role |
|----------|------|
| `OPENAI_API_KEY` | **Required** for CrewAI (research / risk / earnings crews) |
| `LANGSMITH_TRACING`, `LANGSMITH_API_KEY` | Optional OpenTelemetry traces to LangSmith ([observability](docs/ARCHITECTURE.md#8-observability--reporting)) |
| Angel One, Alpha Vantage, Finnhub, GNews, etc. | Optional; improve coverage — see `.env.example` and [data-sources-guide.md](docs/data-sources-guide.md) |

Ports on the host: **10001** Postgres, **10002** Redis, **10003** Keycloak, **10004** MCP, **10005** frontend.

**JWT issuer:** Tokens must have `iss` equal to your configured **public** Keycloak issuer (`KEYCLOAK_PUBLIC_URL/realms/finint`). If you obtain tokens against an internal Docker hostname while the server validates the public issuer, validation fails — use the same issuer the MCP server expects ([§1.4 Auth & enforcement](docs/ARCHITECTURE.md#14-auth--enforcement)).

---

## API quick reference

Base URL: `http://localhost:10004`

| Class | Paths |
|-------|--------|
| Public | `GET /health`, `GET /.well-known/oauth-protected-resource`, `GET /api/status` |
| Authenticated | `POST /mcp`, `POST /api/tool/{name}`, `GET /api/resource?uri=...` |

Example (after obtaining a token from Keycloak):

```bash
curl -s -X POST http://localhost:10004/api/tool/get_stock_quote \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "RELIANCE"}'
```

**Scopes, tier matrix, rate limits (30 / 150 / 500 per hour), and MCP vs REST parity:** [§1.4 Auth & enforcement](docs/ARCHITECTURE.md#14-auth--enforcement), [§5 API & data flow](docs/ARCHITECTURE.md#5-api--data-flow), and [Requirements traceability](docs/ARCHITECTURE.md#requirements-traceability).

---

## Demo users (Keycloak)

| User | Password | Tier |
|------|----------|------|
| `free_user` | `free123` | Free |
| `premium_user` | `premium123` | Premium |
| `analyst_user` | `analyst123` | Analyst |
| `admin` | `admin123` | Admin (tier requests, admin routes) |

Keycloak admin console: http://localhost:10003 — default `admin` / `admin` from Compose (change before any real deployment).

**Smoke test (tier boundary):** call `POST /api/tool/earnings_verdict` with a **free** token → **403**; with **analyst** → **200** (requires valid symbol and OpenAI key). See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for token endpoint examples.

---

## Development

```bash
docker compose up -d --build mcp-server    # or: frontend
docker compose logs -f mcp-server
docker compose exec redis redis-cli FLUSHDB  # clear L2 cache / rate windows
```

**Architecture, CrewAI, tools, and QA:** **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.  
**MCP / REST client setup:** **[docs/MCP.md](docs/MCP.md)**.

---

## Security & operations notes

- Upstream API keys live **only** on the server; the browser uses **short-lived JWTs**.
- CORS is permissive in demo mode; tighten for production ([DEPLOYMENT.md](docs/DEPLOYMENT.md)).
- REST resource bridge and validation behaviour are described under [Auth & enforcement](docs/ARCHITECTURE.md#14-auth--enforcement) and [API & data flow](docs/ARCHITECTURE.md#5-api--data-flow).

---

*README aligned with ARCHITECTURE.md v2.1 — FinInt / W3 MCP.*
