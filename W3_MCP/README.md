# Indian Financial Intelligence — MCP Server

MCP (Model Context Protocol) server that exposes Indian market data, fundamentals, news, mutual funds, filings, and macro indicators as **tiered tools, resources, and prompts**, with **OAuth 2.1 (Keycloak)** and a **Next.js** dashboard. Three product areas are covered: **Research Copilot (PS1)**, **Portfolio risk (PS2)**, and **Earnings season (PS3)**, with **CrewAI** used for analyst-grade cross-source synthesis.

**Documentation**

| Doc | Use it for |
|-----|------------|
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Local Docker, EC2, ports, security groups, public URL / build args |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, auth enforcement, data facade, persistence, requirements traceability |
| [docs/MCP.md](docs/MCP.md) | Connecting MCP clients (Claude, VS Code), Bearer on `/mcp`, REST bridge, catalog URL |

---

## Repository layout (high level)

```
W3_MCP/
├── mcp-server/          # Python FastMCP app: tools, resources, prompts, JWT auth, rate limits, audit, data facade, CrewAI crews
├── frontend/            # Next.js 14 app: research / portfolio / earnings tabs, NextAuth + Keycloak
├── keycloak/            # Realm export (tiers, clients, demo users)
├── db/                  # PostgreSQL init (schema seed)
├── docker-compose.yml   # Orchestrates 5 services
├── .env.example         # Required and optional API keys (with comments)
└── docs/                # DEPLOYMENT, ARCHITECTURE, MCP
```

Source layout inside `mcp-server/src/` and `frontend/` is summarized in [docs/ARCHITECTURE.md — Repo layout](docs/ARCHITECTURE.md#repo-layout).

---

## Run locally

From this directory (where `docker-compose.yml` lives):

```bash
cd W3_MCP

cp .env.example .env
# Set OPENAI_API_KEY (required). Add other keys from .env.example as needed.

docker compose up -d --build
```

First startup may take **1–2 minutes** (Keycloak realm import, health checks).

| URL | What |
|-----|------|
| http://localhost:10005 | Dashboard |
| http://localhost:10004 | MCP server (`/health`, `POST /mcp`, REST bridge `/api/tool/...`) |
| http://localhost:10003 | Keycloak |

**Verify**

```bash
curl -s http://localhost:10004/health
```

**Cloud or custom hostnames** (build args, `OAUTH_RESOURCE_URL`, security groups): [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

---

## Configuration

`OPENAI_API_KEY` is **required** for CrewAI. Other variables (Angel One, Alpha Vantage, Finnhub, GNews, LangSmith, etc.) are **optional** but improve coverage—see **`.env.example`** for names and signup links.

Ports exposed on the host: **10001** Postgres, **10002** Redis, **10003** Keycloak, **10004** MCP, **10005** frontend.

---

## API quick reference

Base URL: `http://localhost:10004`

- **Public:** `GET /health`, `GET /.well-known/oauth-protected-resource`, `GET /api/status`
- **Authenticated (Bearer JWT):** `POST /mcp`, `POST /api/tool/{name}`, `GET /api/resource?uri=...`

Example (after obtaining a token from Keycloak):

```bash
curl -s -X POST http://localhost:10004/api/tool/get_stock_quote \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "RELIANCE"}'
```

Scopes, tier matrices, rate limits (30 / 150 / 500 per hour), admin routes, and native MCP vs REST parity: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — see **Auth & enforcement** and **Requirements traceability**.

---

## Demo users (Keycloak)

| User | Password | Notes |
|------|----------|--------|
| `free_user` | `free123` | Free tier |
| `premium_user` | `premium123` | Premium tier |
| `analyst_user` | `analyst123` | Analyst tier |
| `admin` | `admin123` | Admin flows (e.g. tier requests) |

Keycloak admin console: http://localhost:10003 — default `admin` / `admin` from Compose (change for any real deployment).

---

## Development

```bash
docker compose up -d --build mcp-server    # or frontend
docker compose logs -f mcp-server
docker compose exec redis redis-cli FLUSHDB  # clear cache
```

**Smoke test (tier boundary):** obtain tokens from Keycloak’s token endpoint (password grant is fine for local dev), then call `/api/tool/earnings_verdict` with a **free** token (expect **403**) and an **analyst** token (expect success). Full examples: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) verify section and [docs/ARCHITECTURE.md — Appendix](docs/ARCHITECTURE.md#appendix-rest-tool-call-sequence).

**Architecture and auth:** **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**. **MCP / REST client setup:** **[docs/MCP.md](docs/MCP.md)**.
