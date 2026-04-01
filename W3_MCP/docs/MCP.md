# MCP — clients & HTTP surface

How to reach the FinInt MCP server from **MCP clients** (streamable HTTP) and from **HTTP tools** (REST bridge). This file is intentionally narrow: **no system architecture, data pipeline, or evaluation checklists** — those live in **[ARCHITECTURE.md](ARCHITECTURE.md)**. **Deploy and ports:** **[DEPLOYMENT.md](DEPLOYMENT.md)** and repo **[README.md](../README.md)**.

---

## Contents

1. [Endpoints & transport](#1-endpoints--transport)
2. [Prerequisites](#2-prerequisites)
3. [Claude Desktop](#3-claude-desktop)
4. [Claude.ai (remote MCP)](#4-claudeai-remote-mcp)
5. [VS Code (Copilot MCP)](#5-vs-code-copilot-mcp)
6. [curl: REST bridge & metadata](#6-curl-rest-bridge--metadata)
7. [Authentication (summary)](#7-authentication-summary)
8. [Demo users](#8-demo-users)
9. [Tool catalog](#9-tool-catalog)
10. [Quick reference](#10-quick-reference)

---

## 1. Endpoints & transport

| Surface | URL (local default) | Auth | Role |
|---------|---------------------|------|------|
| **MCP** | `POST http://localhost:10004/mcp` | **Bearer JWT** (required) | Streamable HTTP; `tools/list`, `tools/call`, resources, prompts — tier-filtered lists |
| **REST bridge** | `POST http://localhost:10004/api/tool/{name}` | Bearer JWT | Same tools as JSON-RPC body; **rate limit + audit** on this path (see ARCHITECTURE) |
| **REST resource** | `GET http://localhost:10004/api/resource?uri=...` | Bearer JWT | Read resource by URI; native `/mcp` enforces stricter resource visibility by tier |
| **Discovery** | `GET /.well-known/oauth-protected-resource` | — | RFC 9728 |
| **Catalog** | `GET /api/tools/catalog` | — | JSON list of tools with `required_scopes`, `minimum_tier`, auth URLs |

Tokens are issued by **Keycloak** (`finint` realm). Scopes on the wire are **derived from realm roles** (`free` / `premium` / `analyst`), not from a literal OAuth `scope` claim — details in **ARCHITECTURE.md → Auth & enforcement**.

---

## 2. Prerequisites

Stack running (from repo root):

```bash
cd W3_MCP
cp .env.example .env   # configure keys
docker compose up -d --build
```

Ports and cloud setup: **DEPLOYMENT.md**. Smoke check:

```bash
curl -s http://localhost:10004/health
```

---

## 3. Claude Desktop

Config path examples:

| OS | File |
|----|------|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |

Add (replace `<YOUR_ACCESS_TOKEN>` with a Keycloak access token — see [§8](#8-demo-users) / curl below):

```json
{
  "mcpServers": {
    "finint": {
      "url": "http://localhost:10004/mcp",
      "transport": "streamable-http",
      "headers": {
        "Authorization": "Bearer <YOUR_ACCESS_TOKEN>"
      }
    }
  }
}
```

Restart Claude Desktop. Tokens are short-lived (~minutes); refresh when you see **401**.

**Troubleshooting:** connection refused → compose not up; 403 → tier too low for that tool; tools missing after config change → restart Claude; **streamable-http** needs a current Claude Desktop build.

---

## 4. Claude.ai (remote MCP)

The MCP host must be **publicly reachable** (not only localhost). Use your deployed URL or a tunnel (e.g. ngrok, Cloudflare Tunnel) to port **10004**.

In Claude.ai → Settings → Integrations: URL `https://your-host/mcp`, transport **Streamable HTTP**, authentication **Bearer** with the same Keycloak JWT as above.

---

## 5. VS Code (Copilot MCP)

In `.vscode/settings.json` (or user settings):

```json
{
  "github.copilot.chat.mcpServers": {
    "finint": {
      "url": "http://localhost:10004/mcp",
      "transport": "streamable-http",
      "headers": {
        "Authorization": "Bearer <YOUR_ACCESS_TOKEN>"
      }
    }
  }
}
```

Use `@finint` in Copilot Chat to target this server.

---

## 6. curl: REST bridge & metadata

Obtain a token (example: analyst — use `free_user` / `premium_user` for other tiers):

```bash
export TOKEN=$(curl -s -X POST \
  "http://localhost:10003/realms/finint/protocol/openid-connect/token" \
  -d "grant_type=password&client_id=finint-dashboard&username=analyst_user&password=analyst123" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

Call a tool:

```bash
curl -s -X POST http://localhost:10004/api/tool/get_stock_quote \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"RELIANCE"}' | python3 -m json.tool
```

Read a resource:

```bash
curl -s "http://localhost:10004/api/resource?uri=market://overview" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Protected resource metadata (RFC 9728):

```bash
curl -s http://localhost:10004/.well-known/oauth-protected-resource | python3 -m json.tool
```

---

## 7. Authentication (summary)

```
Client ──► Keycloak (:10003) ──► JWT
              │
              └──► MCP (:10004)  Authorization: Bearer <jwt>
                        │
                        ├── /mcp     … validate JWT, tier → scopes, filter tools/prompts/resources
                        └── /api/tool/* … validate JWT, scopes, rate limit, audit
```

- **Browser app (dashboard):** OAuth 2.1 Authorization Code + **PKCE** via NextAuth → Keycloak.  
- **MCP / curl demos:** password grant to the token endpoint (dev only).  
- **JWT checks:** JWKS, `iss`, `aud`, `exp` — see **ARCHITECTURE.md**.  
- **401 / 403:** REST responses include `WWW-Authenticate` with `resource_metadata` pointing at `/.well-known/oauth-protected-resource` (see **ARCHITECTURE.md**).

---

## 8. Demo users

| Username | Password | Tier |
|----------|----------|------|
| `free_user` | `free123` | Free |
| `premium_user` | `premium123` | Premium |
| `analyst_user` | `analyst123` | Analyst |

Password grant (free tier example):

```bash
curl -s -X POST "http://localhost:10003/realms/finint/protocol/openid-connect/token" \
  -d "grant_type=password&client_id=finint-dashboard&username=free_user&password=free123" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])"
```

**Which scopes each tier gets** is defined in code (`TIER_SCOPES` in `mcp-server/src/config/constants.py`) and summarized under **ARCHITECTURE.md → Auth & enforcement**. **Which scopes each tool needs** is in the catalog below.

---

## 9. Tool catalog

Machine-readable list (names, `required_scopes`, `minimum_tier`, token and metadata URLs):

```bash
curl -s http://localhost:10004/api/tools/catalog | python3 -m json.tool
```

---

## 10. Quick reference

| Endpoint | Method | Auth |
|----------|--------|------|
| `/health` | GET | No |
| `/.well-known/oauth-protected-resource` | GET | No |
| `/api/status` | GET | No |
| `/api/tools/catalog` | GET | No |
| `/mcp` | POST | **Bearer JWT** |
| `/api/tool/{name}` | POST | Bearer JWT |
| `/api/resource?uri=` | GET | Bearer JWT |
| `/api/tier-request` | POST | Bearer JWT |
| `/api/admin/*` | varies | JWT + admin role (see server routes) |

For **sequence diagrams** (REST tool path: JWT → scope → rate limit → tool), see **ARCHITECTURE.md → Appendix: REST tool call sequence**.
