# MCP Connection & Testing Guide

Complete guide for connecting to the FinInt MCP server from **Claude Desktop**, **Claude.ai**, **VS Code**, and **curl**, plus every test scenario required by the AI League #3 evaluation criteria.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Connecting via Claude Desktop](#2-connecting-via-claude-desktop)
3. [Connecting via Claude.ai (Remote MCP)](#3-connecting-via-claudeai-remote-mcp)
4. [Connecting via VS Code (Copilot Agent)](#4-connecting-via-vs-code-copilot-agent)
5. [Connecting via curl (REST Bridge)](#5-connecting-via-curl-rest-bridge)
6. [Authentication Flow](#6-authentication-flow)
7. [Demo Users & Tiers](#7-demo-users--tiers)
8. [PS1 Test Scenarios — Research Copilot](#8-ps1-test-scenarios--research-copilot)
9. [PS2 Test Scenarios — Portfolio Risk Monitor](#9-ps2-test-scenarios--portfolio-risk-monitor)
10. [PS3 Test Scenarios — Earnings Command Center](#10-ps3-test-scenarios--earnings-command-center)
11. [Cross-Source Reasoning Tests](#11-cross-source-reasoning-tests)
12. [Auth Boundary Tests](#12-auth-boundary-tests)
13. [Rate Limiting Tests](#13-rate-limiting-tests)
14. [Evaluation Criteria Checklist](#14-evaluation-criteria-checklist)

---

## 1. Prerequisites

Start the full stack:

```bash
cd W3_MCP
cp .env.example .env    # Fill in API keys
docker compose up -d --build
```

Wait for all services to be healthy:

```bash
docker compose ps
```

| Service    | Host Port | Internal Port | URL                         |
|------------|-----------|---------------|-----------------------------|
| Postgres   | 10001     | 5432          | —                           |
| Redis      | 10002     | 6379          | —                           |
| Keycloak   | 10003     | 8080          | http://localhost:10003       |
| MCP Server | 10004     | 10004         | http://localhost:10004       |
| Frontend   | 10005     | 10005         | http://localhost:10005       |

Verify MCP server is running:

```bash
curl http://localhost:10004/health
# {"status":"healthy","service":"finint-mcp-server","version":"1.0.0",...}
```

---

## 2. Connecting via Claude Desktop

Claude Desktop supports MCP servers natively. The server must be reachable over HTTP.

### Step 1: Locate your Claude Desktop config file

| OS      | Path                                                                 |
|---------|----------------------------------------------------------------------|
| macOS   | `~/Library/Application Support/Claude/claude_desktop_config.json`    |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json`                        |
| Linux   | `~/.config/Claude/claude_desktop_config.json`                        |

### Step 2: Add the MCP server configuration

Open/create the config file and add:

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

### Step 3: Get an access token

You need a Keycloak JWT token. Get one via the password grant:

```bash
# Free tier token
curl -s -X POST "http://localhost:10003/realms/finint/protocol/openid-connect/token" \
  -d "grant_type=password&client_id=finint-dashboard&username=free_user&password=free123" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])"

# Premium tier token
curl -s -X POST "http://localhost:10003/realms/finint/protocol/openid-connect/token" \
  -d "grant_type=password&client_id=finint-dashboard&username=premium_user&password=premium123" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])"

# Analyst tier token
curl -s -X POST "http://localhost:10003/realms/finint/protocol/openid-connect/token" \
  -d "grant_type=password&client_id=finint-dashboard&username=analyst_user&password=analyst123" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])"
```

Paste the resulting token into the `Authorization` header in the config.

> **Note:** Keycloak tokens expire after ~5 minutes. Regenerate when expired.

### Step 4: Restart Claude Desktop

Quit and reopen Claude Desktop. You should see "finint" listed in the MCP servers panel (🔌 icon). Click it to verify tools are discovered.

### Step 5: Test it

Type in Claude Desktop:

```
What's happening with HDFC Bank today?
```

Claude will call `get_stock_quote` and `get_company_news` via MCP automatically.

### Troubleshooting

| Issue | Fix |
|-------|-----|
| "Connection refused" | Ensure `docker compose up -d` is running and MCP server is healthy |
| "401 Unauthorized" | Token expired — regenerate with the curl command above |
| "403 Forbidden" | Tool requires a higher tier — use analyst_user token |
| Tools not showing | Restart Claude Desktop after editing config |
| "Unknown transport" | Update Claude Desktop to latest version (streamable-http requires v1.x+) |

---

## 3. Connecting via Claude.ai (Remote MCP)

Claude.ai supports **remote MCP servers** for Pro/Team/Enterprise plans.

### Option A: Direct Connection (if publicly hosted)

If you deploy the MCP server to a public URL (e.g., via ngrok, Cloudflare Tunnel, or a cloud VM):

1. Go to **claude.ai** → **Settings** → **Integrations** → **Add Integration**
2. Enter:
   - **Name:** `FinInt MCP`
   - **URL:** `https://your-public-url/mcp`
   - **Transport:** Streamable HTTP
   - **Authentication:** Bearer Token → paste your Keycloak JWT
3. Click **Save** and start a new conversation

### Option B: Expose localhost via ngrok

```bash
# Install ngrok: https://ngrok.com/download
ngrok http 10004
```

This gives you a public URL like `https://abc123.ngrok-free.app`. Use:

```
URL: https://abc123.ngrok-free.app/mcp
```

in Claude.ai settings.

### Option C: Expose via Cloudflare Tunnel (persistent)

```bash
# Install: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/
cloudflared tunnel --url http://localhost:10004
```

### Important Notes for Claude.ai

- Claude.ai remote MCP requires the server to be **publicly accessible** (not localhost)
- The MCP endpoint is `http(s)://your-host/mcp` (the `/mcp` path is required)
- Tokens still expire — you'll need to refresh them periodically
- Claude.ai currently supports **streamable HTTP** transport only
- Ensure CORS is properly configured (our server allows `*` origins)

---

## 4. Connecting via VS Code (Copilot Agent)

VS Code's GitHub Copilot supports MCP servers via the agent mode.

### Step 1: Open VS Code settings

Add to `.vscode/settings.json` or your user settings:

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

### Step 2: Use in Copilot Chat

Open Copilot Chat (Ctrl+Shift+I) and ask:

```
@finint What is the stock price of Reliance?
```

---

## 5. Connecting via curl (REST Bridge)

The MCP server exposes a REST bridge at `/api/tool/{tool_name}` for direct HTTP testing. This is the easiest way to verify everything works.

### Get a token

```bash
# Store in a variable for reuse
export TOKEN=$(curl -s -X POST \
  "http://localhost:10003/realms/finint/protocol/openid-connect/token" \
  -d "grant_type=password&client_id=finint-dashboard&username=analyst_user&password=analyst123" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

### Call a tool

```bash
curl -s -X POST http://localhost:10004/api/tool/get_stock_quote \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"RELIANCE"}' | python3 -m json.tool
```

### Read a resource

```bash
curl -s "http://localhost:10004/api/resource?uri=market://overview" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

### Check protected resource metadata (RFC 9728)

```bash
curl -s http://localhost:10004/.well-known/oauth-protected-resource | python3 -m json.tool
```

---

## 6. Authentication Flow

```
┌──────────┐     ┌──────────────┐     ┌────────────┐
│  Client   │────▶│   Keycloak   │────▶│  JWT Token │
│ (Claude/  │     │ :10003       │     │  (5min TTL)│
│  curl)    │◀────│ /realms/     │◀────│            │
└──────────┘     │ finint/      │     └────────────┘
     │           │ protocol/    │
     │           │ openid-      │
     │           │ connect/     │
     │           │ token        │
     │           └──────────────┘
     │
     │  Authorization: Bearer <token>
     ▼
┌──────────────┐
│  MCP Server  │  1. Validate JWT (JWKS from Keycloak)
│  :10004      │  2. Extract tier from token claims
│              │  3. Check scope: TOOL_SCOPE_MAP[tool] ∈ TIER_SCOPES[tier]
│  /mcp        │  4. Rate limit: Redis sliding window
│  /api/tool/* │  5. Audit log: Postgres
└──────────────┘
```

### OAuth 2.1 + PKCE

- **Auth Server:** Keycloak 24.0 (separated from MCP server)
- **Client ID:** `finint-dashboard`
- **Grant type:** Authorization Code + PKCE (for browser), Password Grant (for CLI/demo)
- **Token format:** JWT with custom `tier` claim and `realm_access.roles` scopes
- **Token validation:** JWKS endpoint at `http://keycloak:8080/realms/finint/protocol/openid-connect/certs`
- **Protected Resource Metadata:** `GET /.well-known/oauth-protected-resource` (RFC 9728)

---

## 7. Demo Users & Tiers

| Username        | Password      | Tier    | Tools | Rate Limit  |
|-----------------|---------------|---------|-------|-------------|
| `free_user`     | `free123`     | Free    | 14    | 30 calls/hr |
| `premium_user`  | `premium123`  | Premium | 30    | 150 calls/hr|
| `analyst_user`  | `analyst123`  | Analyst | 44    | 500 calls/hr|

### Tier → Scope Mapping

| Scope                | Free | Premium | Analyst |
|----------------------|------|---------|---------|
| `market:read`        | ✅   | ✅      | ✅      |
| `mf:read`            | ✅   | ✅      | ✅      |
| `news:read`          | ✅   | ✅      | ✅      |
| `watchlist:read`     | ✅   | ✅      | ✅      |
| `watchlist:write`    | ✅   | ✅      | ✅      |
| `fundamentals:read`  | ❌   | ✅      | ✅      |
| `technicals:read`    | ❌   | ✅      | ✅      |
| `macro:read`         | ❌   | ✅      | ✅      |
| `portfolio:read`     | ❌   | ✅      | ✅      |
| `filings:read`       | ❌   | ✅      | ✅      |
| `filings:deep`       | ❌   | ❌      | ✅      |
| `research:generate`  | ❌   | ❌      | ✅      |

---

## 8. PS1 Test Scenarios — Research Copilot

### Must-Show Demo Scenario 1: Free User — "What's happening with HDFC Bank?"

```bash
export FREE=$(curl -s -X POST "http://localhost:10003/realms/finint/protocol/openid-connect/token" \
  -d "grant_type=password&client_id=finint-dashboard&username=free_user&password=free123" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# ✅ Free can get quote
curl -s -X POST http://localhost:10004/api/tool/get_stock_quote \
  -H "Authorization: Bearer $FREE" -H "Content-Type: application/json" \
  -d '{"symbol":"HDFCBANK"}' | python3 -m json.tool

# ✅ Free can get news
curl -s -X POST http://localhost:10004/api/tool/get_company_news \
  -H "Authorization: Bearer $FREE" -H "Content-Type: application/json" \
  -d '{"symbol":"HDFCBANK"}' | python3 -m json.tool

# ❌ Free CANNOT get fundamentals → 403
curl -s -X POST http://localhost:10004/api/tool/get_financial_statements \
  -H "Authorization: Bearer $FREE" -H "Content-Type: application/json" \
  -d '{"symbol":"HDFCBANK"}' | python3 -m json.tool
# Expected: {"error":"Insufficient scope for tool 'get_financial_statements'","error_code":"FORBIDDEN",...}
```

### Must-Show Demo Scenario 2: Premium User — quick_analysis for INFY

```bash
export PREMIUM=$(curl -s -X POST "http://localhost:10003/realms/finint/protocol/openid-connect/token" \
  -d "grant_type=password&client_id=finint-dashboard&username=premium_user&password=premium123" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# ✅ Quote
curl -s -X POST http://localhost:10004/api/tool/get_stock_quote \
  -H "Authorization: Bearer $PREMIUM" -H "Content-Type: application/json" \
  -d '{"symbol":"INFY"}' | python3 -m json.tool

# ✅ Key ratios
curl -s -X POST http://localhost:10004/api/tool/get_key_ratios \
  -H "Authorization: Bearer $PREMIUM" -H "Content-Type: application/json" \
  -d '{"symbol":"INFY"}' | python3 -m json.tool

# ✅ News
curl -s -X POST http://localhost:10004/api/tool/get_company_news \
  -H "Authorization: Bearer $PREMIUM" -H "Content-Type: application/json" \
  -d '{"symbol":"INFY"}' | python3 -m json.tool

# ✅ Shareholding
curl -s -X POST http://localhost:10004/api/tool/get_shareholding_pattern \
  -H "Authorization: Bearer $PREMIUM" -H "Content-Type: application/json" \
  -d '{"symbol":"INFY"}' | python3 -m json.tool

# ❌ Premium CANNOT do cross-source analysis → 403
curl -s -X POST http://localhost:10004/api/tool/cross_reference_signals \
  -H "Authorization: Bearer $PREMIUM" -H "Content-Type: application/json" \
  -d '{"symbol":"INFY"}' | python3 -m json.tool
```

### Must-Show Demo Scenario 3: Analyst — deep_dive for RELIANCE (5+ sources)

```bash
export ANALYST=$(curl -s -X POST "http://localhost:10003/realms/finint/protocol/openid-connect/token" \
  -d "grant_type=password&client_id=finint-dashboard&username=analyst_user&password=analyst123" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# ✅ Cross-source signal analysis (pulls from 3+ APIs, identifies confirmations/contradictions)
curl -s -X POST http://localhost:10004/api/tool/cross_reference_signals \
  -H "Authorization: Bearer $ANALYST" -H "Content-Type: application/json" \
  -d '{"symbol":"RELIANCE"}' | python3 -m json.tool

# ✅ Research brief (synthesises price + fundamentals + news + shareholding + MF + macro)
curl -s -X POST http://localhost:10004/api/tool/generate_research_brief \
  -H "Authorization: Bearer $ANALYST" -H "Content-Type: application/json" \
  -d '{"symbol":"RELIANCE"}' | python3 -m json.tool

# ✅ Company comparison
curl -s -X POST http://localhost:10004/api/tool/compare_companies \
  -H "Authorization: Bearer $ANALYST" -H "Content-Type: application/json" \
  -d '{"symbols":"RELIANCE,TCS,INFY"}' | python3 -m json.tool
```

### PS1 Individual Tool Tests

```bash
# Market Data Tools (Free tier)
curl -s -X POST http://localhost:10004/api/tool/get_stock_quote -H "Authorization: Bearer $FREE" -H "Content-Type: application/json" -d '{"symbol":"TCS"}'
curl -s -X POST http://localhost:10004/api/tool/get_price_history -H "Authorization: Bearer $FREE" -H "Content-Type: application/json" -d '{"symbol":"TCS","period":"1mo"}'
curl -s -X POST http://localhost:10004/api/tool/get_index_data -H "Authorization: Bearer $FREE" -H "Content-Type: application/json" -d '{"index":"NIFTY 50"}'
curl -s -X POST http://localhost:10004/api/tool/get_top_gainers_losers -H "Authorization: Bearer $FREE" -H "Content-Type: application/json" -d '{}'

# Mutual Fund Tools (Free tier)
curl -s -X POST http://localhost:10004/api/tool/search_mutual_funds -H "Authorization: Bearer $FREE" -H "Content-Type: application/json" -d '{"query":"HDFC Flexi"}'
curl -s -X POST http://localhost:10004/api/tool/get_fund_nav -H "Authorization: Bearer $FREE" -H "Content-Type: application/json" -d '{"scheme_code":"118989"}'

# News Tools (Free tier)
curl -s -X POST http://localhost:10004/api/tool/get_company_news -H "Authorization: Bearer $FREE" -H "Content-Type: application/json" -d '{"symbol":"RELIANCE"}'
curl -s -X POST http://localhost:10004/api/tool/get_market_news -H "Authorization: Bearer $FREE" -H "Content-Type: application/json" -d '{}'

# Fundamental Tools (Premium tier)
curl -s -X POST http://localhost:10004/api/tool/get_financial_statements -H "Authorization: Bearer $PREMIUM" -H "Content-Type: application/json" -d '{"symbol":"INFY"}'
curl -s -X POST http://localhost:10004/api/tool/get_key_ratios -H "Authorization: Bearer $PREMIUM" -H "Content-Type: application/json" -d '{"symbol":"INFY"}'
curl -s -X POST http://localhost:10004/api/tool/get_shareholding_pattern -H "Authorization: Bearer $PREMIUM" -H "Content-Type: application/json" -d '{"symbol":"INFY"}'
curl -s -X POST http://localhost:10004/api/tool/get_quarterly_results -H "Authorization: Bearer $PREMIUM" -H "Content-Type: application/json" -d '{"symbol":"INFY"}'

# Technical Indicators (Premium tier)
curl -s -X POST http://localhost:10004/api/tool/get_technical_indicators -H "Authorization: Bearer $PREMIUM" -H "Content-Type: application/json" -d '{"symbol":"INFY"}'

# Macro Tools (Premium tier)
curl -s -X POST http://localhost:10004/api/tool/get_rbi_rates -H "Authorization: Bearer $PREMIUM" -H "Content-Type: application/json" -d '{}'
curl -s -X POST http://localhost:10004/api/tool/get_inflation_data -H "Authorization: Bearer $PREMIUM" -H "Content-Type: application/json" -d '{}'

# Cross-Source Tools (Analyst tier)
curl -s -X POST http://localhost:10004/api/tool/cross_reference_signals -H "Authorization: Bearer $ANALYST" -H "Content-Type: application/json" -d '{"symbol":"RELIANCE"}'
curl -s -X POST http://localhost:10004/api/tool/generate_research_brief -H "Authorization: Bearer $ANALYST" -H "Content-Type: application/json" -d '{"symbol":"RELIANCE"}'
curl -s -X POST http://localhost:10004/api/tool/compare_companies -H "Authorization: Bearer $ANALYST" -H "Content-Type: application/json" -d '{"symbols":"TCS,INFY,WIPRO"}'
```

---

## 9. PS2 Test Scenarios — Portfolio Risk Monitor

### Must-Show Demo: Build portfolio → detect risks → get alerts

```bash
# Step 1: Add holdings (Free tier — uses watchlist:write)
curl -s -X POST http://localhost:10004/api/tool/add_to_portfolio \
  -H "Authorization: Bearer $FREE" -H "Content-Type: application/json" \
  -d '{"symbol":"RELIANCE","quantity":50,"avg_price":2400}' | python3 -m json.tool

curl -s -X POST http://localhost:10004/api/tool/add_to_portfolio \
  -H "Authorization: Bearer $FREE" -H "Content-Type: application/json" \
  -d '{"symbol":"TCS","quantity":30,"avg_price":3500}' | python3 -m json.tool

curl -s -X POST http://localhost:10004/api/tool/add_to_portfolio \
  -H "Authorization: Bearer $FREE" -H "Content-Type: application/json" \
  -d '{"symbol":"INFY","quantity":40,"avg_price":1400}' | python3 -m json.tool

# Step 2: Portfolio summary (Free tier)
curl -s -X POST http://localhost:10004/api/tool/get_portfolio_summary \
  -H "Authorization: Bearer $FREE" -H "Content-Type: application/json" \
  -d '{}' | python3 -m json.tool

# Step 3: Health check & concentration risk (Premium tier — portfolio:read)
curl -s -X POST http://localhost:10004/api/tool/portfolio_health_check \
  -H "Authorization: Bearer $PREMIUM" -H "Content-Type: application/json" \
  -d '{}' | python3 -m json.tool

curl -s -X POST http://localhost:10004/api/tool/check_concentration_risk \
  -H "Authorization: Bearer $PREMIUM" -H "Content-Type: application/json" \
  -d '{}' | python3 -m json.tool

# Step 4: Premium analysis — MF overlap, macro sensitivity, sentiment
curl -s -X POST http://localhost:10004/api/tool/check_mf_overlap \
  -H "Authorization: Bearer $PREMIUM" -H "Content-Type: application/json" \
  -d '{}' | python3 -m json.tool

curl -s -X POST http://localhost:10004/api/tool/check_macro_sensitivity \
  -H "Authorization: Bearer $PREMIUM" -H "Content-Type: application/json" \
  -d '{}' | python3 -m json.tool

curl -s -X POST http://localhost:10004/api/tool/detect_sentiment_shift \
  -H "Authorization: Bearer $PREMIUM" -H "Content-Type: application/json" \
  -d '{}' | python3 -m json.tool

# Step 5: Analyst-only — AI risk report & what-if
curl -s -X POST http://localhost:10004/api/tool/portfolio_risk_report \
  -H "Authorization: Bearer $ANALYST" -H "Content-Type: application/json" \
  -d '{}' | python3 -m json.tool

curl -s -X POST http://localhost:10004/api/tool/what_if_analysis \
  -H "Authorization: Bearer $ANALYST" -H "Content-Type: application/json" \
  -d '{"scenario":"RBI cuts repo rate by 25bps"}' | python3 -m json.tool
```

### PS2 Auth Boundary Test

```bash
# ❌ Free tries portfolio_health_check (now Premium — portfolio:read)
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:10004/api/tool/portfolio_health_check \
  -H "Authorization: Bearer $FREE" -H "Content-Type: application/json" -d '{}'
# Expected: 403

# ❌ Free tries check_concentration_risk (now Premium — portfolio:read)
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:10004/api/tool/check_concentration_risk \
  -H "Authorization: Bearer $FREE" -H "Content-Type: application/json" -d '{}'
# Expected: 403

# ❌ Free tries check_mf_overlap (Premium — portfolio:read)
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:10004/api/tool/check_mf_overlap \
  -H "Authorization: Bearer $FREE" -H "Content-Type: application/json" -d '{}'
# Expected: 403

# ❌ Free tries analyst tool
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:10004/api/tool/portfolio_risk_report \
  -H "Authorization: Bearer $FREE" -H "Content-Type: application/json" -d '{}'
# Expected: 403

# ✅ Premium → portfolio_health_check = 200
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:10004/api/tool/portfolio_health_check \
  -H "Authorization: Bearer $PREMIUM" -H "Content-Type: application/json" -d '{}'
# Expected: 200

# ❌ Premium tries analyst tool
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:10004/api/tool/what_if_analysis \
  -H "Authorization: Bearer $PREMIUM" -H "Content-Type: application/json" -d '{"scenario":"test"}'
# Expected: 403
```

---

## 10. PS3 Test Scenarios — Earnings Command Center

### Must-Show Demo Scenario 1: Pre-earnings (e.g., "INFY")

```bash
# System pulls EPS history, shareholding, options, news sentiment → structured preview

# ✅ Free: earnings calendar
curl -s -X POST http://localhost:10004/api/tool/get_earnings_calendar \
  -H "Authorization: Bearer $FREE" -H "Content-Type: application/json" \
  -d '{"weeks":4}' | python3 -m json.tool

# ✅ Premium: EPS history with YoY/QoQ
curl -s -X POST http://localhost:10004/api/tool/get_eps_history \
  -H "Authorization: Bearer $PREMIUM" -H "Content-Type: application/json" \
  -d '{"symbol":"INFY","quarters":8}' | python3 -m json.tool

# ✅ Premium: Pre-earnings profile (4Q results + ratios + FII trend + options + sentiment)
curl -s -X POST http://localhost:10004/api/tool/get_pre_earnings_profile \
  -H "Authorization: Bearer $PREMIUM" -H "Content-Type: application/json" \
  -d '{"symbol":"INFY"}' | python3 -m json.tool

# ✅ Premium: Analyst expectations (extrapolated from history)
curl -s -X POST http://localhost:10004/api/tool/get_analyst_expectations \
  -H "Authorization: Bearer $PREMIUM" -H "Content-Type: application/json" \
  -d '{"symbol":"INFY"}' | python3 -m json.tool

# ✅ Premium: Option chain (OI, IV, PCR, max pain)
curl -s -X POST http://localhost:10004/api/tool/get_option_chain \
  -H "Authorization: Bearer $PREMIUM" -H "Content-Type: application/json" \
  -d '{"symbol":"INFY"}' | python3 -m json.tool
```

### Must-Show Demo Scenario 2: Post-earnings — results_flash

```bash
# System fetches BSE filing → parses revenue/profit/EPS → compares to estimates → checks market reaction

# ✅ Premium: Post-results price reaction (day0/+1/+2, volume spike)
curl -s -X POST http://localhost:10004/api/tool/get_post_results_reaction \
  -H "Authorization: Bearer $PREMIUM" -H "Content-Type: application/json" \
  -d '{"symbol":"INFY"}' | python3 -m json.tool

# ✅ Premium: Beat/miss analysis
curl -s -X POST http://localhost:10004/api/tool/compare_actual_vs_expected \
  -H "Authorization: Bearer $PREMIUM" -H "Content-Type: application/json" \
  -d '{"symbol":"INFY"}' | python3 -m json.tool

# ✅ Analyst: Full cross-source earnings verdict (BSE filing + NSE price + shareholding + news + estimates)
curl -s -X POST http://localhost:10004/api/tool/earnings_verdict \
  -H "Authorization: Bearer $ANALYST" -H "Content-Type: application/json" \
  -d '{"symbol":"INFY"}' | python3 -m json.tool
```

### Must-Show Demo Scenario 3: Cross-company comparison

```bash
# ✅ Analyst: TCS vs INFY side-by-side on all dimensions
curl -s -X POST http://localhost:10004/api/tool/compare_quarterly_performance \
  -H "Authorization: Bearer $ANALYST" -H "Content-Type: application/json" \
  -d '{"symbols":"TCS,INFY"}' | python3 -m json.tool

# ✅ Analyst: Earnings season dashboard (who beat, who missed, sector trends)
curl -s -X POST http://localhost:10004/api/tool/earnings_season_dashboard \
  -H "Authorization: Bearer $ANALYST" -H "Content-Type: application/json" \
  -d '{}' | python3 -m json.tool
```

### PS3 Auth Boundary Tests

```bash
# ✅ Free → earnings calendar = 200
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:10004/api/tool/get_earnings_calendar \
  -H "Authorization: Bearer $FREE" -H "Content-Type: application/json" -d '{"weeks":2}'
# Expected: 200

# ❌ Free → get_eps_history = 403 (Premium)
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:10004/api/tool/get_eps_history \
  -H "Authorization: Bearer $FREE" -H "Content-Type: application/json" -d '{"symbol":"INFY"}'
# Expected: 403

# ❌ Free → get_filing_document = 403 (Analyst)
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:10004/api/tool/get_filing_document \
  -H "Authorization: Bearer $FREE" -H "Content-Type: application/json" -d '{"symbol":"INFY","filing_id":"test"}'
# Expected: 403

# ✅ Premium → get_pre_earnings_profile = 200
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:10004/api/tool/get_pre_earnings_profile \
  -H "Authorization: Bearer $PREMIUM" -H "Content-Type: application/json" -d '{"symbol":"INFY"}'
# Expected: 200

# ❌ Premium → earnings_verdict = 403 (Analyst)
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:10004/api/tool/earnings_verdict \
  -H "Authorization: Bearer $PREMIUM" -H "Content-Type: application/json" -d '{"symbol":"INFY"}'
# Expected: 403

# ✅ Analyst → earnings_verdict = 200
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:10004/api/tool/earnings_verdict \
  -H "Authorization: Bearer $ANALYST" -H "Content-Type: application/json" -d '{"symbol":"INFY"}'
# Expected: 200

# ✅ Analyst → earnings_season_dashboard = 200
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:10004/api/tool/earnings_season_dashboard \
  -H "Authorization: Bearer $ANALYST" -H "Content-Type: application/json" -d '{}'
# Expected: 200
```

---

## 11. Cross-Source Reasoning Tests

These are the **differentiator** tests — they verify that tools combine data from 3+ APIs and identify confirmations/contradictions.

### Test 1: cross_reference_signals (PS1 — Analyst)

```bash
curl -s -X POST http://localhost:10004/api/tool/cross_reference_signals \
  -H "Authorization: Bearer $ANALYST" -H "Content-Type: application/json" \
  -d '{"symbol":"TCS"}' | python3 -m json.tool
```

**Expected output must contain:**
- Data from **3+ different sources** (e.g., NSE price, yfinance fundamentals, Finnhub news, BSE shareholding)
- **Confirmations** — e.g., "Revenue growth of 8% [BSE filing] supported by FII increase [shareholding data]"
- **Contradictions** — e.g., "Stock fell 4% [NSE] despite strong results [BSE filing]"
- **Citations** with specific values — e.g., `"Source: NSE, LTP ₹3,456"`, `"Source: yfinance, P/E 28.5"`

### Test 2: earnings_verdict (PS3 — Analyst)

```bash
curl -s -X POST http://localhost:10004/api/tool/earnings_verdict \
  -H "Authorization: Bearer $ANALYST" -H "Content-Type: application/json" \
  -d '{"symbol":"INFY"}' | python3 -m json.tool
```

**Expected output must combine:**
- **BSE filing data** — EPS, revenue, PE ratio (from yfinance/fundamentals)
- **NSE price reaction** — stock price change on results day
- **Shareholding changes** — FII increase/decrease
- **News sentiment** — positive/negative/neutral from news APIs
- **Estimates vs actual** — beat/miss verdict with surprise %
- **Contradictions** — e.g., "beat but stock fell"
- **Narrative** — human-readable explanation of the "why"
- **Citations** — each data point attributed to its source

### Test 3: generate_research_brief (PS1 — Analyst)

```bash
curl -s -X POST http://localhost:10004/api/tool/generate_research_brief \
  -H "Authorization: Bearer $ANALYST" -H "Content-Type: application/json" \
  -d '{"symbol":"RELIANCE"}' | python3 -m json.tool
```

**Expected:** Synthesises price data, fundamentals, MF exposure, news, filings, and macro context into a structured research note with evidence citations from each source.

### Test 4: compare_quarterly_performance (PS3 — Analyst)

```bash
curl -s -X POST http://localhost:10004/api/tool/compare_quarterly_performance \
  -H "Authorization: Bearer $ANALYST" -H "Content-Type: application/json" \
  -d '{"symbols":"TCS,INFY,WIPRO"}' | python3 -m json.tool
```

**Expected:** Side-by-side comparison of EPS, revenue, PE, PB, ROE, D/E, market cap, price change, EPS YoY growth, FII change for each company.

---

## 12. Auth Boundary Tests

### Complete Auth Matrix — Expected HTTP Status Codes

| Tool                          | No Token | Free | Premium | Analyst | Scope              |
|-------------------------------|----------|------|---------|---------|--------------------|
| `get_stock_quote`             | 401      | 200  | 200     | 200     | `market:read`      |
| `get_price_history`           | 401      | 200  | 200     | 200     | `market:read`      |
| `get_index_data`              | 401      | 200  | 200     | 200     | `market:read`      |
| `get_top_gainers_losers`      | 401      | 200  | 200     | 200     | `market:read`      |
| `get_company_news`            | 401      | 200  | 200     | 200     | `news:read`        |
| `get_market_news`             | 401      | 200  | 200     | 200     | `news:read`        |
| `search_mutual_funds`         | 401      | 200  | 200     | 200     | `mf:read`          |
| `get_fund_nav`                | 401      | 200  | 200     | 200     | `mf:read`          |
| `get_earnings_calendar`       | 401      | 200  | 200     | 200     | `market:read`      |
| `get_past_results_dates`      | 401      | 200  | 200     | 200     | `market:read`      |
| `add_to_portfolio`            | 401      | 200  | 200     | 200     | `watchlist:write`  |
| `remove_from_portfolio`       | 401      | 200  | 200     | 200     | `watchlist:write`  |
| `get_portfolio_summary`       | 401      | 200  | 200     | 200     | `watchlist:read`   |
| `portfolio_health_check`      | 401      | 403  | 200     | 200     | `portfolio:read`   |
| `check_concentration_risk`    | 401      | 403  | 200     | 200     | `portfolio:read`   |
| `get_key_ratios`              | 401      | 403  | 200     | 200     | `fundamentals:read`|
| `get_financial_statements`    | 401      | 403  | 200     | 200     | `fundamentals:read`|
| `get_shareholding_pattern`    | 401      | 403  | 200     | 200     | `fundamentals:read`|
| `get_quarterly_results`       | 401      | 403  | 200     | 200     | `fundamentals:read`|
| `get_technical_indicators`    | 401      | 403  | 200     | 200     | `technicals:read`  |
| `get_news_sentiment`          | 401      | 200  | 200     | 200     | `news:read`        |
| `get_rbi_rates`               | 401      | 403  | 200     | 200     | `macro:read`       |
| `compare_funds`               | 401      | 403  | 200     | 200     | `fundamentals:read`|
| `get_corporate_filings`       | 401      | 403  | 200     | 200     | `filings:read`     |
| `get_eps_history`             | 401      | 403  | 200     | 200     | `fundamentals:read`|
| `get_pre_earnings_profile`    | 401      | 403  | 200     | 200     | `fundamentals:read`|
| `get_analyst_expectations`    | 401      | 403  | 200     | 200     | `fundamentals:read`|
| `get_post_results_reaction`   | 401      | 403  | 200     | 200     | `fundamentals:read`|
| `compare_actual_vs_expected`  | 401      | 403  | 200     | 200     | `fundamentals:read`|
| `get_option_chain`            | 401      | 403  | 200     | 200     | `fundamentals:read`|
| `check_mf_overlap`            | 401      | 403  | 200     | 200     | `portfolio:read`   |
| `check_macro_sensitivity`     | 401      | 403  | 200     | 200     | `portfolio:read`   |
| `detect_sentiment_shift`      | 401      | 403  | 200     | 200     | `portfolio:read`   |
| `get_inflation_data`          | 401      | 403  | 403     | 200     | `macro:historical` |
| `cross_reference_signals`     | 401      | 403  | 403     | 200     | `research:generate`|
| `generate_research_brief`     | 401      | 403  | 403     | 200     | `research:generate`|
| `compare_companies`           | 401      | 403  | 403     | 200     | `research:generate`|
| `earnings_verdict`            | 401      | 403  | 403     | 200     | `research:generate`|
| `earnings_season_dashboard`   | 401      | 403  | 403     | 200     | `research:generate`|
| `compare_quarterly_performance`| 401     | 403  | 403     | 200     | `research:generate`|
| `portfolio_risk_report`       | 401      | 403  | 403     | 200     | `research:generate`|
| `what_if_analysis`            | 401      | 403  | 403     | 200     | `research:generate`|
| `get_filing_document`         | 401      | 403  | 403     | 200     | `filings:deep`     |
| `parse_quarterly_filing`      | 401      | 403  | 403     | 200     | `filings:deep`     |

**HTTP Response Headers:**
- **401:** `WWW-Authenticate: Bearer realm="finint", resource_metadata="http://localhost:10004/.well-known/oauth-protected-resource"`
- **403:** `WWW-Authenticate: Bearer realm="finint", error="insufficient_scope", scope="{required_scope}"`
- **429:** `Retry-After: {seconds}`

### Automated Auth Boundary Test Script

```bash
#!/bin/bash
# Run all auth boundary tests

KC="http://localhost:10003/realms/finint/protocol/openid-connect/token"
MCP="http://localhost:10004/api/tool"

get_token() {
  curl -s -X POST "$KC" \
    -d "grant_type=password&client_id=finint-dashboard&username=$1&password=$2" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])"
}

FREE=$(get_token free_user free123)
PREMIUM=$(get_token premium_user premium123)
ANALYST=$(get_token analyst_user analyst123)

test_tool() {
  local tool=$1 expected=$2 token=$3 tier=$4 body=${5:-'{}'}
  local code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$MCP/$tool" \
    -H "Authorization: Bearer $token" -H "Content-Type: application/json" -d "$body")
  if [ "$code" = "$expected" ]; then
    echo "✅ $tier → $tool = $code"
  else
    echo "❌ $tier → $tool = $code (expected $expected)"
  fi
}

echo "=== No Token ==="
code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$MCP/get_stock_quote" -H "Content-Type: application/json" -d '{"symbol":"TCS"}')
echo "No token → get_stock_quote = $code (expected 401)"

echo ""
echo "=== Free Tier ==="
test_tool get_stock_quote 200 "$FREE" Free '{"symbol":"TCS"}'
test_tool get_company_news 200 "$FREE" Free '{"symbol":"TCS"}'
test_tool get_earnings_calendar 200 "$FREE" Free '{"weeks":2}'
test_tool get_portfolio_summary 200 "$FREE" Free
test_tool portfolio_health_check 403 "$FREE" Free
test_tool check_concentration_risk 403 "$FREE" Free
test_tool compare_funds 403 "$FREE" Free '{"scheme_codes":"118989,100356"}'
test_tool get_key_ratios 403 "$FREE" Free '{"symbol":"TCS"}'
test_tool get_eps_history 403 "$FREE" Free '{"symbol":"TCS"}'
test_tool get_inflation_data 403 "$FREE" Free
test_tool cross_reference_signals 403 "$FREE" Free '{"symbol":"TCS"}'
test_tool earnings_verdict 403 "$FREE" Free '{"symbol":"TCS"}'
test_tool get_filing_document 403 "$FREE" Free '{"symbol":"TCS","filing_id":"x"}'

echo ""
echo "=== Premium Tier ==="
test_tool get_stock_quote 200 "$PREMIUM" Premium '{"symbol":"TCS"}'
test_tool get_key_ratios 200 "$PREMIUM" Premium '{"symbol":"TCS"}'
test_tool get_eps_history 200 "$PREMIUM" Premium '{"symbol":"TCS"}'
test_tool get_option_chain 200 "$PREMIUM" Premium '{"symbol":"TCS"}'
test_tool portfolio_health_check 200 "$PREMIUM" Premium
test_tool check_concentration_risk 200 "$PREMIUM" Premium
test_tool compare_funds 200 "$PREMIUM" Premium '{"scheme_codes":"118989,100356"}'
test_tool get_inflation_data 403 "$PREMIUM" Premium
test_tool cross_reference_signals 403 "$PREMIUM" Premium '{"symbol":"TCS"}'
test_tool earnings_verdict 403 "$PREMIUM" Premium '{"symbol":"TCS"}'
test_tool portfolio_risk_report 403 "$PREMIUM" Premium

echo ""
echo "=== Analyst Tier ==="
test_tool get_stock_quote 200 "$ANALYST" Analyst '{"symbol":"TCS"}'
test_tool get_inflation_data 200 "$ANALYST" Analyst
test_tool cross_reference_signals 200 "$ANALYST" Analyst '{"symbol":"TCS"}'
test_tool generate_research_brief 200 "$ANALYST" Analyst '{"symbol":"TCS"}'
test_tool earnings_verdict 200 "$ANALYST" Analyst '{"symbol":"TCS"}'
test_tool earnings_season_dashboard 200 "$ANALYST" Analyst
test_tool compare_quarterly_performance 200 "$ANALYST" Analyst '{"symbols":"TCS,INFY"}'
test_tool portfolio_risk_report 200 "$ANALYST" Analyst
test_tool what_if_analysis 200 "$ANALYST" Analyst '{"scenario":"RBI cuts 25bps"}'
test_tool get_filing_document 200 "$ANALYST" Analyst '{"symbol":"TCS","filing_id":"latest"}'
```

---

## 13. Tool Catalog & Symbol Validation

### OpenAPI-Style Tool Catalog

The server auto-generates a tool catalog from the registered tools at:

```bash
curl -s http://localhost:10004/api/tools/catalog | python3 -m json.tool
```

**Response includes:**
- `tool_count` — total registered tools (44)
- `tiers` — tools per tier with rate limits (Free: 14, Premium: 32, Analyst: 44)
- `tools[]` — each with `name`, `endpoint`, `method`, `required_scope`, `minimum_tier`
- `auth` — OAuth token endpoint and resource metadata URL

### Symbol Validation

`add_to_portfolio` and `get_stock_quote` validate symbols before accepting them:

```bash
# ❌ Invalid symbol — rejected
curl -s -X POST http://localhost:10004/api/tool/add_to_portfolio \
  -H "Authorization: Bearer $FREE" -H "Content-Type: application/json" \
  -d '{"symbol":"RANDOM","quantity":1,"avg_price":100}' | python3 -m json.tool
# Returns: {"error": "Symbol 'RANDOM' not found...", "error_code": "SYMBOL_NOT_FOUND"}

# ✅ Valid symbol — accepted
curl -s -X POST http://localhost:10004/api/tool/add_to_portfolio \
  -H "Authorization: Bearer $FREE" -H "Content-Type: application/json" \
  -d '{"symbol":"TCS","quantity":10,"avg_price":3500}' | python3 -m json.tool
```

---

## 14. Rate Limiting Tests

```bash
# Rapid-fire 35 requests as free user (limit: 30/hr) — last 5 should get 429
export FREE=$(curl -s -X POST "http://localhost:10003/realms/finint/protocol/openid-connect/token" \
  -d "grant_type=password&client_id=finint-dashboard&username=free_user&password=free123" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

for i in $(seq 1 35); do
  code=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    http://localhost:10004/api/tool/get_stock_quote \
    -H "Authorization: Bearer $FREE" -H "Content-Type: application/json" \
    -d '{"symbol":"TCS"}')
  echo "Request $i: HTTP $code"
done
# Requests 31-35 should return 429 with Retry-After header
```

---

## 14. Evaluation Criteria Checklist

Based on the AI League #3 evaluation rubric (same for all use cases):

### MCP Server Design & Compliance (25%)

| Criteria | Status | How to Verify |
|----------|--------|---------------|
| Correct tools with proper JSON schemas | ✅ | `curl http://localhost:10004/mcp` → tools/list |
| Correct resources with URI patterns | ✅ | `earnings://calendar/upcoming`, `watchlist://*/stocks`, etc. |
| Correct prompts with arguments | ✅ | `quick_analysis`, `deep_dive`, `earnings_preview`, etc. |
| Streamable HTTP transport | ✅ | MCP endpoint at `/mcp` with streamable-http |
| Capability negotiation | ✅ | FastMCP handles `initialize` handshake |
| Tier-aware tool discovery | ✅ | `TierToolFilter` hides tools user can't access |
| Error handling | ✅ | Graceful degradation, fallback chains, circuit breakers |
| Pagination / caching | ✅ | Redis L2 cache, in-memory L1, TTL per data type |
| Tools return structured JSON | ✅ | All tools return `{data, source, cache_status, timestamp, disclaimer}` |

### Authentication & Authorization (25%)

| Criteria | Status | How to Verify |
|----------|--------|---------------|
| OAuth 2.1 + PKCE end-to-end | ✅ | Keycloak PKCE flow via frontend login |
| Protected Resource Metadata | ✅ | `GET /.well-known/oauth-protected-resource` |
| Tiered access enforced (tools, resources, prompts) | ✅ | See auth boundary tests above |
| Rate limiting per tier with 429 | ✅ | Redis sliding window: Free 30/hr, Premium 150/hr, Analyst 500/hr |
| Proper 401/403 with WWW-Authenticate | ✅ | 401: `Bearer realm="finint", resource_metadata="..."`, 403: `error="insufficient_scope", scope="..."` |
| Auth server separated from MCP server | ✅ | Keycloak (:10003) separate from MCP (:10004) |
| Upstream API key isolation | ✅ | Keys in server `.env`, never sent to clients |

### Cross-Source Reasoning Quality (25%)

| Criteria | Status | How to Verify |
|----------|--------|---------------|
| Cross-source tools combine 3+ APIs | ✅ | `cross_reference_signals`, `earnings_verdict` |
| Contradictions/confirmations identified | ✅ | `contradictions[]` field in verdict |
| Specific evidence citations | ✅ | `citations[]` with source, data_point, value |
| Cross-source adds insight beyond individual APIs | ✅ | Narrative explains "why" behind market reaction |

### System Design & Technical Depth (15%)

| Criteria | Status | How to Verify |
|----------|--------|---------------|
| Caching strategy (per-type TTLs) | ✅ | `constants.py`: quotes 30s, news 15m, fundamentals 24h |
| Rate limiting (per-user, per-tier) | ✅ | Redis sliding window with tier-based limits |
| Upstream failure handling | ✅ | Fallback chains: angel_one→yfinance, alpha_vantage→yfinance |
| Audit logging | ✅ | Every tool call logged to Postgres with user, tier, tool, timestamp |

### Demo & Usability (10%)

| Criteria | Status | How to Verify |
|----------|--------|---------------|
| Works with MCP client (Claude Desktop) | ✅ | See Section 2 |
| Demo: auth flow → tool discovery → use tools → permission boundary → tier upgrade | ✅ | See Sections 8-12 |
| Clear setup instructions | ✅ | README.md + this guide |
| API documentation | ✅ | README.md has full tool reference |

### Deployment (Bonus)

| Criteria | Status | How to Verify |
|----------|--------|---------------|
| One-command Docker Compose | ✅ | `docker compose up -d --build` |
| Claude Desktop integration demonstrated | ✅ | See Section 2 |
| `.env.example` with API key sign-up links | ✅ | `.env.example` in repo root |
| Health-check endpoint | ✅ | `GET /health` and `GET /api/status` |

---

## Quick Reference: All MCP Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/health` | GET | No | Server health check |
| `/.well-known/oauth-protected-resource` | GET | No | RFC 9728 OAuth discovery |
| `/api/status` | GET | No | Upstream API status |
| `/api/tools/catalog` | GET | No | OpenAPI-style tool catalog (44 tools, scopes, tiers) |
| `/mcp` | POST | Bearer JWT | MCP Streamable HTTP transport |
| `/api/tool/{name}` | POST | Bearer JWT | REST bridge — call any MCP tool |
| `/api/resource?uri={uri}` | GET | Bearer JWT | REST bridge — read MCP resource |
| `/api/tier-request` | POST | Bearer JWT | Request tier upgrade |
| `/api/admin/tier-requests` | GET | No | List pending upgrade requests |
