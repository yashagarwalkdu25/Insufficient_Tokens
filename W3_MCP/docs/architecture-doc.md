# Production architecture: Indian Financial Intelligence MCP Server with CrewAI

## System overview

The architecture has **six horizontal layers**, each with a clear responsibility boundary:

1. **MCP Client Layer** — Claude Desktop, VS Code, custom apps, WhatsApp bots
2. **API Gateway + Auth Layer** — OAuth 2.1, rate limiting, audit logging, tier enforcement
3. **MCP Server Core** — FastMCP (Python), tool/resource/prompt registry, scope enforcement
4. **Intelligence Layer** — CrewAI multi-agent reasoning engine + Redis/Postgres state
5. **Data Aggregation Facade** — Adapter pattern, circuit breakers, fallback chains, ISIN normalization
6. **External Data Sources** — Angel One, MFapi.in, BSE, Finnhub, Alpha Vantage, RBI DBIE

Two supporting systems sit alongside: **Keycloak** (separate auth server) and **Docker Compose infrastructure** (AWS Mumbai).

---

## Why CrewAI fits this problem

The hackathon/startup challenge is fundamentally a **cross-source reasoning problem**. A user asks "What's happening with Reliance?" and the system must:
- Fetch price data (Angel One)
- Pull fundamentals (Alpha Vantage / yfinance)
- Get recent news + sentiment (Finnhub / GNews)
- Check shareholding pattern changes (BSE)
- Assess macro context (RBI rates, USD/INR)
- **Synthesize all of this into a coherent narrative with confidence scores**

This maps perfectly to CrewAI's hierarchical process where specialized agents collect data in parallel and a synthesizer agent combines their findings.

### CrewAI advantages over manual orchestration:
- **Built-in delegation**: The manager agent decides which sub-agents to invoke based on the query
- **Automatic context passing**: Output from the data collector flows to the analyst flows to the synthesizer
- **Pydantic output validation**: Forces structured JSON output (signals, contradictions, confidence) — exactly what the MCP spec requires
- **Different LLMs per agent**: Use GPT-4o-mini for cheap data collection, GPT-4o for expensive reasoning
- **Conditional tasks**: If the data collector finds fewer than 3 sources, trigger a backup collection task
- **Memory**: Agents remember prior analyses within a session, avoiding redundant API calls

---

## Layer-by-layer architecture

### Layer 1: MCP clients

No custom work needed. The MCP protocol handles client compatibility. Your server exposes Streamable HTTP and any MCP-compatible client connects.

**Supported clients**: Claude Desktop, VS Code (Copilot MCP), Cursor, custom apps via MCP SDK, WhatsApp bot (via middleware that translates messages to MCP tool calls).

### Layer 2: API gateway + auth

```
┌──────────────────────────────────────────────────┐
│  API Gateway (FastAPI reverse proxy)             │
│                                                  │
│  ┌─────────────┐  ┌──────────┐  ┌────────────┐  │
│  │ OAuth 2.1   │  │ Rate     │  │ Audit      │  │
│  │ PKCE verify │  │ Limiter  │  │ Logger     │  │
│  └─────────────┘  └──────────┘  └────────────┘  │
│                                                  │
│  ┌─────────────────────────────────────────────┐ │
│  │ Tier Enforcer                               │ │
│  │ Token scopes → allowed tools mapping        │ │
│  │ Free: market:read, mf:read                  │ │
│  │ Premium: + fundamentals:read, technicals    │ │
│  │ Analyst: + research:generate, filings:deep  │ │
│  └─────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘
         ↕ Token validation via Keycloak JWKS
┌──────────────────────────────────────────────────┐
│  Keycloak Auth Server (separate container)       │
│  - Issues JWT tokens with tier-based scopes      │
│  - PKCE code challenge verification              │
│  - /.well-known/oauth-protected-resource         │
│  - User registration with tier assignment        │
└──────────────────────────────────────────────────┘
```

**Rate limits enforced per tier:**
- Free: 30 calls/hour
- Premium: 150 calls/hour  
- Analyst: 500 calls/hour

**Implementation**: Use a sliding window counter in Redis keyed by `user_id:window_start`. On 429, return `Retry-After` header.

### Layer 3: MCP server core

```python
# server.py — FastMCP server with tier-aware tool discovery
from mcp.server.fastmcp import FastMCP

app = FastMCP("indian-financial-intelligence")

@app.tool()
async def get_stock_quote(symbol: str, ctx: Context) -> dict:
    """Get live quote for an NSE/BSE ticker."""
    # Scope check happens in middleware
    return await data_facade.get_price(symbol)

@app.tool()  
async def cross_reference_signals(symbol: str, ctx: Context) -> dict:
    """Cross-source analysis combining price, fundamentals, 
    news sentiment, and macro context. Analyst tier only."""
    # This triggers the CrewAI reasoning engine
    return await crewai_engine.analyze(symbol, ctx.user_tier)

@app.resource("market://overview")
async def market_overview() -> str:
    """Nifty 50, Sensex, top gainers/losers, FII/DII flows."""
    return await data_facade.get_market_overview()

@app.resource("watchlist://{user_id}/stocks")
async def user_watchlist(user_id: str) -> str:
    """User's personal stock watchlist."""
    return await db.get_watchlist(user_id)

@app.prompt()
async def deep_dive(symbol: str) -> str:
    """Comprehensive analysis pulling all available data."""
    return f"Perform a deep-dive analysis of {symbol}..."
```

**Key design decisions:**
- Tools return **structured JSON**, not narrative text (the LLM client handles narrative)
- Every response includes `source` metadata (API name, timestamp, cache status)
- Tier-aware tool discovery: Free users don't even see `cross_reference_signals` in the tool list
- `ctx.user_tier` is extracted from the validated JWT token

### Layer 4: CrewAI reasoning engine

This is the core innovation. Here's the full CrewAI implementation:

```python
# crewai_engine.py
from crewai import Agent, Task, Crew, Process
from pydantic import BaseModel
from typing import List, Optional

# === Pydantic Output Models ===
class Signal(BaseModel):
    source: str           # "Angel One API", "Finnhub", etc.
    signal_type: str      # "price", "fundamental", "sentiment", "macro"
    direction: float      # -1.0 (bearish) to +1.0 (bullish)
    confidence: float     # 0.0 to 1.0
    evidence: str         # "LTP ₹2,456 (+2.3% today)"
    timestamp: str

class CrossSourceAnalysis(BaseModel):
    symbol: str
    signals: List[Signal]
    contradictions: List[str]
    synthesis: str
    overall_confidence: float
    disclaimer: str

# === Agent Definitions ===

data_collector = Agent(
    role="Market Data Collector",
    goal="Fetch real-time price, volume, and technical data for the given stock",
    backstory="""You are a meticulous data collector specializing in Indian 
    stock markets. You use Angel One SmartAPI for real-time prices, check 
    BSE for recent filings, and MFapi.in for mutual fund exposure. You always 
    cite the exact source and timestamp of every data point.""",
    llm=ChatOpenAI(model="gpt-4o-mini", temperature=0),  # Cheap, fast
    tools=[angel_one_tool, bse_scraper_tool, mfapi_tool],
    memory=True,
    max_iter=10,
    allow_delegation=False,
    verbose=True
)

fundamental_analyst = Agent(
    role="Fundamental Analyst", 
    goal="Evaluate the company's financial health using ratios, earnings, and filings",
    backstory="""You are a CFA charterholder specializing in Indian equities. 
    You analyze P/E, P/B, ROE, ROCE, debt/equity, and compare against sector 
    averages. You understand Ind AS accounting standards and can parse BSE 
    quarterly result filings.""",
    llm=ChatOpenAI(model="gpt-4o", temperature=0.3),  # Needs reasoning
    tools=[alpha_vantage_tool, bse_filing_parser_tool, yfinance_tool],
    memory=True,
    max_iter=10,
    allow_delegation=False
)

sentiment_analyst = Agent(
    role="News Sentiment Analyst",
    goal="Assess market sentiment from news, social signals, and institutional flows",
    backstory="""You analyze Indian financial news using Finnhub and GNews APIs. 
    You score sentiment on a -1 to +1 scale. You distinguish between company-
    specific news and sector/macro news. You flag if negative sentiment is 
    driven by company issues vs broader market fear.""",
    llm=ChatOpenAI(model="gpt-4o-mini", temperature=0.2),
    tools=[finnhub_news_tool, gnews_tool, finbert_scorer_tool],
    memory=True,
    max_iter=10,
    allow_delegation=False
)

macro_analyst = Agent(
    role="Macro & Risk Analyst",
    goal="Assess how macroeconomic factors impact the stock and sector",
    backstory="""You specialize in connecting RBI monetary policy, inflation data, 
    forex movements, and sector rotation patterns to individual stock impact. 
    You know that banking stocks benefit from rate hikes (higher NIM) while 
    real estate suffers (higher mortgage costs).""",
    llm=ChatOpenAI(model="gpt-4o", temperature=0.3),
    tools=[rbi_dbie_tool, sector_mapper_tool, mf_overlap_tool],
    memory=True,
    max_iter=10,
    allow_delegation=False
)

synthesizer = Agent(
    role="Research Synthesizer",
    goal="Combine all signals into a coherent cross-source analysis with confidence scores",
    backstory="""You are the final analyst who synthesizes inputs from the data 
    collector, fundamental analyst, sentiment analyst, and macro analyst. You 
    detect contradictions (e.g., price falling but fundamentals strong), assign 
    confidence scores, and produce a structured research output. You NEVER give 
    buy/sell/hold advice — only analysis with cited sources.""",
    llm=ChatOpenAI(model="gpt-4o", temperature=0.5),
    memory=True,
    max_iter=15,
    allow_delegation=False
)

# === Task Definitions ===

def build_crew(symbol: str) -> Crew:
    collect_task = Task(
        description=f"Fetch real-time market data for {symbol}: current price, "
                    f"volume, 52-week range, today's movement, delivery percentage. "
                    f"Also check if any mutual funds hold this stock.",
        expected_output="JSON with price data, volume stats, and MF exposure",
        agent=data_collector,
    )

    fundamental_task = Task(
        description=f"Analyze fundamentals for {symbol}: P/E, P/B, ROE, ROCE, "
                    f"debt-to-equity, recent quarterly results (revenue, PAT, EPS), "
                    f"and compare to sector median.",
        expected_output="JSON with key ratios, quarterly comparison, and sector context",
        agent=fundamental_analyst,
    )

    sentiment_task = Task(
        description=f"Analyze news sentiment for {symbol} over the last 7 days. "
                    f"Score overall sentiment -1 to +1. Identify if sentiment is "
                    f"company-specific or sector/macro driven.",
        expected_output="JSON with sentiment score, key articles, and driver classification",
        agent=sentiment_analyst,
    )

    macro_task = Task(
        description=f"Assess macro impact on {symbol}: current RBI repo rate, "
                    f"recent rate changes, CPI trend, USD/INR movement, and how "
                    f"these affect this stock's sector specifically.",
        expected_output="JSON with macro indicators and sector-specific impact assessment",
        agent=macro_analyst,
    )

    synthesis_task = Task(
        description=f"Synthesize all findings for {symbol} into a cross-source "
                    f"analysis. Detect any contradictions between signals (e.g., "
                    f"price falling but fundamentals improving). Assign confidence "
                    f"scores. Cite every source with timestamps.",
        expected_output="Complete CrossSourceAnalysis with signals, contradictions, "
                       "and synthesis narrative",
        agent=synthesizer,
        output_pydantic=CrossSourceAnalysis,  # Enforces structured output
    )

    return Crew(
        agents=[data_collector, fundamental_analyst, 
                sentiment_analyst, macro_analyst, synthesizer],
        tasks=[collect_task, fundamental_task, 
               sentiment_task, macro_task, synthesis_task],
        process=Process.sequential,  # Collect → Analyze → Synthesize
        memory=True,
        verbose=True,
        planning=True,  # CrewAI plans execution before starting
    )


async def analyze(symbol: str, user_tier: str) -> dict:
    crew = build_crew(symbol)
    result = crew.kickoff(inputs={"symbol": symbol})
    return result.pydantic.dict()  # Returns validated CrossSourceAnalysis
```

### Why sequential process, not hierarchical?

For the MCP server use case, **sequential is better than hierarchical** because:
- The data flow is predictable: collect → analyze → synthesize
- Hierarchical adds a manager agent that burns extra API tokens deciding who does what
- Sequential gives deterministic execution order, easier to debug
- Cost: Sequential uses ~4 LLM calls; hierarchical would use ~8-10

**Use hierarchical only for**: The `deep_dive` prompt where the query is open-ended and the manager needs to decide which agents are relevant.

### Layer 5: Data aggregation facade

```python
# data_facade.py
class DataFacade:
    def __init__(self):
        self.l1_cache = LRUCache(maxsize=1000)  # In-memory
        self.l2_cache = Redis(host="redis", port=6379)
        self.circuit_breakers = {
            "angel_one": CircuitBreaker(failure_threshold=5, recovery_time=60),
            "alpha_vantage": CircuitBreaker(failure_threshold=3, recovery_time=300),
            "yfinance": CircuitBreaker(failure_threshold=10, recovery_time=120),
            "finnhub": CircuitBreaker(failure_threshold=5, recovery_time=60),
            "bse": CircuitBreaker(failure_threshold=5, recovery_time=120),
        }
        self.isin_mapper = ISINMapper()  # Maps symbols across exchanges
    
    async def get_price(self, symbol: str) -> dict:
        isin = self.isin_mapper.resolve(symbol)
        cache_key = f"price:{isin}"
        
        # L1 check
        if cached := self.l1_cache.get(cache_key):
            return {**cached, "_cache": "l1", "_age_seconds": cached["_ttl_remaining"]}
        
        # L2 check
        if cached := await self.l2_cache.get(cache_key):
            self.l1_cache.set(cache_key, cached)
            return {**cached, "_cache": "l2"}
        
        # Fallback chain: Angel One → yfinance → stale cache
        for source in self.price_chain:
            if self.circuit_breakers[source.name].is_open:
                continue
            try:
                data = await source.fetch(isin)
                await self._write_cache(cache_key, data, ttl=30)
                return {**data, "_cache": "miss", "_source": source.name}
            except Exception as e:
                self.circuit_breakers[source.name].record_failure()
        
        # All sources failed — return stale data with warning
        stale = await self.l2_cache.get(cache_key, ignore_ttl=True)
        if stale:
            return {**stale, "_stale": True, "_warning": "All sources unavailable"}
        raise DataUnavailableError(f"No data available for {symbol}")
```

### Layer 6: External data source adapters

Each data source gets a dedicated adapter class that handles:
- Authentication (API keys stored in env vars, never exposed to clients)
- Response normalization to internal schema
- Error handling specific to that API's failure modes
- Rate limit awareness (tracks remaining quota)

```python
# Example: Angel One adapter
class AngelOneAdapter:
    name = "angel_one"
    
    async def fetch(self, isin: str) -> dict:
        symbol = self.isin_to_nse_symbol(isin)
        quote = await self.smart_api.get_quote(symbol)
        return {
            "symbol": symbol,
            "isin": isin,
            "ltp": quote["ltp"],
            "change_pct": quote["percentChange"],
            "volume": quote["tradeVolume"],
            "open": quote["open"],
            "high": quote["high"],
            "low": quote["low"],
            "close": quote["close"],
            "timestamp": datetime.utcnow().isoformat(),
            "source": "Angel One SmartAPI",
        }
```

---

## Docker Compose deployment

```yaml
version: "3.8"
services:
  mcp-server:
    build: ./mcp-server
    ports: ["10004:10004"]
    env_file: .env
    depends_on: [redis, postgres, keycloak]
    
  keycloak:
    image: quay.io/keycloak/keycloak:24.0
    command: start-dev
    ports: ["10003:8080"]
    environment:
      KEYCLOAK_ADMIN: admin
      KEYCLOAK_ADMIN_PASSWORD: admin
    
  redis:
    image: redis:7-alpine
    ports: ["10002:6379"]
    
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: finint
      POSTGRES_USER: finint
      POSTGRES_PASSWORD: finint
    ports: ["10001:5432"]
```

**One command to run everything**: `docker compose up -d`

---

## CrewAI custom tools (mapped to MCP tools)

Each CrewAI tool wraps a data facade adapter and is also exposed as an MCP tool:

```python
from crewai.tools import BaseTool

class AngelOneQuoteTool(BaseTool):
    name: str = "get_stock_quote"
    description: str = "Get real-time stock quote from Angel One SmartAPI"
    
    def _run(self, symbol: str) -> str:
        data = asyncio.run(data_facade.get_price(symbol))
        return json.dumps(data)

class BSEFilingTool(BaseTool):
    name: str = "get_corporate_filings"
    description: str = "Get recent BSE corporate filings for a company"
    
    def _run(self, symbol: str, filing_type: str = "results") -> str:
        data = asyncio.run(data_facade.get_filings(symbol, filing_type))
        return json.dumps(data)

class FinBERTSentimentTool(BaseTool):
    name: str = "score_news_sentiment"
    description: str = "Score financial news sentiment using FinBERT model"
    
    def _run(self, articles: list) -> str:
        scores = finbert_model.predict(articles)
        return json.dumps({"scores": scores, "average": mean(scores)})
```

---

## How a real query flows through the system

**User asks**: "What's happening with HDFC Bank?"

1. **MCP Client** → sends `cross_reference_signals("HDFCBANK")` via Streamable HTTP
2. **Gateway** → validates Bearer token → checks scopes (needs `research:generate`) → passes to MCP server
3. **MCP Server** → routes to `cross_reference_signals` tool → triggers CrewAI engine
4. **CrewAI Manager** → creates execution plan → delegates to 4 agents in parallel
5. **Data Collector** → Angel One: LTP ₹1,654, +1.8% → BSE: No new filings → MFapi: In 47 of top 50 large-cap MF schemes
6. **Fundamental Analyst** → Alpha Vantage: P/E 19.2, ROE 16.8%, NIM expanding → yfinance: Q3 PAT +18% YoY
7. **Sentiment Analyst** → Finnhub: 12 articles, 8 positive (RBI rate pause helps banking) → GNews: 3 neutral macro pieces
8. **Macro Analyst** → RBI DBIE: Repo rate 6.5% (unchanged) → CPI 4.2% (within target) → USD/INR stable at 83.4
9. **Synthesizer** → Combines all signals:
   - Price: +0.6 (positive momentum)
   - Fundamental: +0.8 (strong metrics, NIM expanding)
   - Sentiment: +0.5 (positive, sector-driven)
   - Macro: +0.4 (stable rates favorable for banks)
   - **No contradictions detected**
   - **Overall confidence: 0.82**
10. **Pydantic validation** → Ensures output matches `CrossSourceAnalysis` schema
11. **MCP Server** → Returns structured JSON with citations to client
12. **LLM Client** → Converts JSON to natural language narrative for user

Total latency: ~8-15 seconds (dominated by LLM inference, not API calls due to caching).

---

## Key architectural decisions and tradeoffs

| Decision | Choice | Why | Tradeoff |
|---|---|---|---|
| CrewAI process | Sequential for standard queries, Hierarchical for deep_dive | Predictable, debuggable, cheaper | Less flexible than full hierarchical |
| LLM per agent | GPT-4o-mini for data collection, GPT-4o for analysis | 10x cost difference; collection doesn't need reasoning | Weaker model may miss edge cases in data extraction |
| Cache layers | L1 in-memory + L2 Redis | 97%+ hit rate, <5ms for hot data | Memory pressure on server for L1 |
| Auth server | Keycloak (separate container) | MCP spec requires separate auth server | Extra container to manage |
| Primary data source | Angel One SmartAPI | Free, licensed, real-time, reliable | Requires Angel One account |
| Output format | Pydantic-validated JSON | MCP spec requires structured data, not narrative | LLM sometimes fights the format constraints |
| Deployment | AWS Mumbai (ap-south-1) | RBI data localization, low latency for Indian users | Slightly more expensive than some regions |
