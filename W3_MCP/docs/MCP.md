# MCP — clients & HTTP surface

How to reach the FinInt MCP server from **MCP clients** (streamable HTTP) and from **HTTP tools** (REST bridge). This file is intentionally narrow: **no system architecture, data pipeline, or evaluation checklists** — those live in **[ARCHITECTURE.md](ARCHITECTURE.md)**. **Deploy and ports:** **[DEPLOYMENT.md](DEPLOYMENT.md)** and repo **[README.md](../README.md)**.

---

## Contents

1. [Endpoints & transport](#1-endpoints--transport)
2. [Prerequisites](#2-prerequisites)
3. [Claude Desktop](#3-claude-desktop)
4. [Cursor](#4-cursor)
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

Add (replace `<YOUR_ACCESS_TOKEN>` with a Keycloak access token — see [§8](#8-demo-users)):

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

## 4. Cursor

Use **Streamable HTTP** to the same MCP path as other clients. **Global** config: `~/.cursor/mcp.json`. **Project** config: `.cursor/mcp.json` in your repo (do not commit real tokens).

- **URL:** `http://localhost:10004/mcp` locally, or `http://<public-host>:10004/mcp` when the MCP port is reachable (see **DEPLOYMENT.md** for security groups).
- **Header:** `Authorization: Bearer <access_token>` — obtain a JWT from Keycloak ([§8](#8-demo-users)); tokens expire quickly.

Example shape (field names can vary slightly by Cursor version; prefer **Settings → MCP** if the UI is clearer):

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

`NEXT_PUBLIC_*` / dashboard URLs do not apply here: the IDE talks to **port 10004** with a **Bearer** token, not the browser OAuth flow.

**Deployed (EC2) and logs like `HTTP 404` / `Invalid OAuth error response` / raw body `Not Found`:** Cursor is trying **OAuth discovery** (no stored token). (1) Prefer **`headers.Authorization`** with a JWT from Keycloak so it skips that flow. (2) On the server, **`/.well-known/oauth-protected-resource`** must list an **`authorization_servers`** URL your laptop can reach — set **`KEYCLOAK_PUBLIC_URL`** on the **mcp-server** service to `http://<public-host>:10003` (Compose does this from **`W3_PUBLIC_HOST`** in `docker-compose.ec2.yml`). (3) **Keycloak** must expose RFC 8414 authorization-server metadata (the stack uses **Keycloak 26.5+** in Compose; **24.x** makes this discovery **404**). After upgrading Keycloak, recreate the container / re-import realm as needed.

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

Use a **password grant** against Keycloak’s token endpoint (dev/demo only). Client **`finint-dashboard`** must have **Direct access grants** enabled (`Client not allowed for direct access grants` → Keycloak Admin → **Clients** → `finint-dashboard` → enable **Direct access grants** → **Save**). **Postman:** `POST` the same URL with **Body → x-www-form-urlencoded**: `grant_type=password`, `client_id=finint-dashboard`, `username`, `password` ([§8](#8-demo-users)).

On EC2, use your public host for `:10003` / `:10004` (see **DEPLOYMENT.md**).

```bash
TOKEN=$(curl -s -X POST "http://localhost:10003/realms/finint/protocol/openid-connect/token" \
  -d "grant_type=password&client_id=finint-dashboard&username=analyst_user&password=analyst123" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -sS -X POST "http://localhost:10004/api/tool/get_stock_quote" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"symbol":"RELIANCE"}'

curl -sS "http://localhost:10004/.well-known/oauth-protected-resource"
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

Realm import sets longer **dev-oriented** lifetimes (see `keycloak/realm-export.json`): access token **4h** (`expires_in`), SSO/client session max **30d** (drives **`refresh_expires_in`**). Existing Keycloak data is not updated when you edit the JSON — use **Realm settings → Tokens** (and **Sessions**) in the admin UI, or re-import after a fresh Keycloak volume.

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
