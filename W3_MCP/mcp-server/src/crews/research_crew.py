"""PS1 Research Crew — 5-agent parallel pipeline for cross-source stock analysis.

Architecture: 4 data-gathering agents run IN PARALLEL (async_execution=True),
then a synthesizer agent runs sequentially to combine all findings.
This cuts execution time by ~4x compared to sequential."""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any

import structlog
from crewai import Agent, Crew, Process, Task
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

os.environ.setdefault("LANGCHAIN_TRACING_V2", os.environ.get("LANGCHAIN_TRACING_V2", "true"))
os.environ.setdefault("CREWAI_TRACING_ENABLED", "true")
os.environ.setdefault("CREWAI_TELEMETRY_OPT_IN", "true")


# ---------------------------------------------------------------------------
# Custom CrewAI Tools (wrap data facade calls for sync agent usage)
# ---------------------------------------------------------------------------

def _run_async(coro):
    """Run an async coroutine from a sync context (CrewAI thread pool).

    CrewAI executes tools in ThreadPoolExecutor threads which have no
    event loop.  We create a fresh loop per call, run the coroutine,
    then close it.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class StockQuoteTool(BaseTool):
    name: str = "get_stock_quote"
    description: str = "Get real-time stock quote (LTP, change, volume) for an NSE/BSE ticker."

    def _run(self, symbol: str) -> str:
        from ..data_facade.facade import data_facade
        result = _run_async(data_facade.get_price(symbol))
        return json.dumps(result, default=str)


class FundamentalsTool(BaseTool):
    name: str = "get_fundamentals"
    description: str = "Get fundamental ratios (P/E, ROE, debt/equity) for a stock."

    def _run(self, symbol: str) -> str:
        from ..data_facade.facade import data_facade
        result = _run_async(data_facade.get_fundamentals(symbol))
        return json.dumps(result, default=str)


class NewsTool(BaseTool):
    name: str = "get_company_news"
    description: str = "Get recent news articles for a company from Finnhub/GNews."

    def _run(self, symbol: str) -> str:
        from ..data_facade.facade import data_facade
        result = _run_async(data_facade.get_news(symbol, days=7))
        return json.dumps(result, default=str)


class MacroTool(BaseTool):
    name: str = "get_macro_data"
    description: str = "Get RBI macro indicators: repo rate, CPI, GDP, USD/INR."

    def _run(self, **kwargs: Any) -> str:
        from ..data_facade.facade import data_facade
        result = _run_async(data_facade.get_macro())
        return json.dumps(result, default=str)


class ShareholdingTool(BaseTool):
    name: str = "get_shareholding"
    description: str = "Get shareholding pattern (promoter, FII, DII, retail %) for a stock."

    def _run(self, symbol: str) -> str:
        from ..data_facade.facade import data_facade
        result = _run_async(data_facade.get_shareholding(symbol))
        return json.dumps(result, default=str)


# ---------------------------------------------------------------------------
# Output model (Pydantic, enforced on final task)
# ---------------------------------------------------------------------------

class SignalOutput(BaseModel):
    source: str
    signal_type: str
    direction: float = Field(ge=-1.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str
    timestamp: str = ""


class CitationOutput(BaseModel):
    source: str
    data_point: str
    value: str = ""
    timestamp: str = ""


class CrossSourceAnalysisOutput(BaseModel):
    symbol: str
    signals: list[SignalOutput] = []
    contradictions: list[str] = []
    synthesis: str = ""
    overall_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    citations: list[CitationOutput] = []
    disclaimer: str = "AI-generated analysis. Not investment advice."


# ---------------------------------------------------------------------------
# Crew builder
# ---------------------------------------------------------------------------

def _build_research_crew(symbol: str) -> Crew:
    """Construct the 5-agent sequential research crew for *symbol*."""
    from ..config.settings import settings

    llm_fast = f"openai/{settings.openai_model_fast}"
    llm_reasoning = f"openai/{settings.openai_model_reasoning}"

    data_collector = Agent(
        role="Market Data Collector",
        goal=f"Fetch real-time price, volume, and technical data for {symbol} and cite every data point with its source",
        backstory=(
            "Meticulous data collector specialising in Indian stock markets. "
            "You use Angel One SmartAPI / yfinance for real-time prices and BSE India for filings. "
            "CRITICAL: For every data point you report, you MUST state the source name "
            "(e.g. 'Angel One SmartAPI', 'yfinance', 'BSE India') and the timestamp. "
            "Example: 'LTP ₹2,456 (+2.3% today) [Source: Angel One SmartAPI, 2026-03-28T17:30:00Z]'"
        ),
        llm=llm_fast,
        tools=[StockQuoteTool(), ShareholdingTool()],
        memory=True,
        max_iter=8,
        allow_delegation=False,
        verbose=False,
    )

    fundamental_analyst = Agent(
        role="Fundamental Analyst",
        goal=f"Evaluate {symbol}'s financial health using ratios and cite Alpha Vantage / yfinance as source",
        backstory=(
            "CFA charterholder specialising in Indian equities. Analyses P/E, P/B, "
            "ROE, ROCE, debt/equity and compares against sector averages. "
            "CRITICAL: Tag every ratio with its source — e.g. 'P/E: 19.2 [Source: Alpha Vantage]', "
            "'ROE: 16.8% [Source: yfinance]'. If data is unavailable, say so explicitly."
        ),
        llm=llm_reasoning,
        tools=[FundamentalsTool()],
        memory=True,
        max_iter=8,
        allow_delegation=False,
        verbose=False,
    )

    sentiment_analyst = Agent(
        role="News Sentiment Analyst",
        goal=f"Assess market sentiment for {symbol} from Finnhub and GNews articles with scored sentiment",
        backstory=(
            "Analyses Indian financial news from Finnhub and GNews APIs. Scores "
            "sentiment -1 to +1 and distinguishes company-specific vs sector/macro drivers. "
            "CRITICAL: Cite article titles and source names — e.g. "
            "'Sentiment: +0.4 from 8 articles [Source: Finnhub]. Key article: "
            "\"TCS wins $2B deal\" (positive, company-specific)'. "
            "Distinguish: is negative sentiment due to the company or broader market fears?"
        ),
        llm=llm_fast,
        tools=[NewsTool()],
        memory=True,
        max_iter=8,
        allow_delegation=False,
        verbose=False,
    )

    macro_analyst = Agent(
        role="Macro & Risk Analyst",
        goal=f"Assess how RBI rates, inflation, and forex affect {symbol} citing RBI DBIE as source",
        backstory=(
            "Connects RBI monetary policy, inflation, and forex to sector/stock impact. "
            "Banking stocks benefit from rate hikes (higher NIM), real estate suffers. "
            "CRITICAL: Cite 'RBI DBIE' as source for repo rate, CPI, GDP data — e.g. "
            "'Repo rate: 6.5% (unchanged) [Source: RBI DBIE]'. "
            "State sector-specific impact explicitly."
        ),
        llm=llm_reasoning,
        tools=[MacroTool()],
        memory=True,
        max_iter=8,
        allow_delegation=False,
        verbose=False,
    )

    synthesizer = Agent(
        role="Research Synthesizer",
        goal=f"Combine all signals into a cross-source analysis for {symbol} with explicit source citations and contradiction detection",
        backstory=(
            "Final analyst who synthesises inputs from data collector, fundamental analyst, "
            "sentiment analyst, and macro analyst into a single coherent narrative. "
            "CRITICAL RULES:\n"
            "1. CITE EVERY SOURCE by name: Angel One/yfinance (price), Alpha Vantage/yfinance "
            "(fundamentals), Finnhub/GNews (news sentiment), BSE India (filings/shareholding), "
            "RBI DBIE (macro).\n"
            "2. For each signal, state: source name, data point, direction (-1 to +1), and confidence.\n"
            "3. DETECT CONTRADICTIONS explicitly — e.g. 'Price fell 4% [Angel One] BUT quarterly "
            "results show 8% revenue growth [BSE filing] AND FII holding increased 2% [BSE shareholding]. "
            "News sentiment is negative due to US recession fears [Finnhub], not company-specific issues.'\n"
            "4. State what CONFIRMS vs what CONTRADICTS across sources.\n"
            "5. NEVER give buy/sell/hold advice — only analysis with cited sources.\n"
            "6. Include a disclaimer that this is AI-generated and not investment advice."
        ),
        llm=llm_reasoning,
        memory=True,
        max_iter=10,
        allow_delegation=False,
        verbose=False,
    )

    # Tasks — first 4 run IN PARALLEL (async_execution=True)
    collect_task = Task(
        description=(
            f"Fetch real-time market data for {symbol} using your tools. Report: "
            f"current price (LTP), change %, volume, 52-week range, and shareholding pattern. "
            f"IMPORTANT: Tag every data point with [Source: <source_name>] and timestamp."
        ),
        expected_output=(
            "Structured data with price, volume, shareholding — each tagged with source name and timestamp. "
            "Example: 'LTP: ₹2,456 (+2.3%) [Source: yfinance, 2026-03-28]'"
        ),
        agent=data_collector,
        async_execution=True,
    )

    fundamental_task = Task(
        description=(
            f"Analyse fundamentals for {symbol} using your tools. Report: P/E, P/B, ROE, ROCE, "
            f"debt-to-equity, EPS, revenue growth. Compare against sector averages if available. "
            f"IMPORTANT: Tag every ratio with [Source: Alpha Vantage] or [Source: yfinance]."
        ),
        expected_output=(
            "Key ratios with source citations. "
            "Example: 'P/E: 19.2 [Source: Alpha Vantage], ROE: 16.8% [Source: yfinance]'"
        ),
        agent=fundamental_analyst,
        async_execution=True,
    )

    sentiment_task = Task(
        description=(
            f"Analyse news sentiment for {symbol} over the last 7 days using your tools. "
            f"Score overall sentiment -1 to +1. List key articles with titles. "
            f"Classify: is sentiment driven by company-specific news or broader market/sector fears? "
            f"IMPORTANT: Tag with [Source: Finnhub] or [Source: GNews]."
        ),
        expected_output=(
            "Sentiment score with article summaries and source citations. "
            "Example: 'Sentiment: +0.4 from 8 articles [Source: Finnhub]. "
            "Key: \"HDFC Bank NIM expands\" (positive, company-specific)'"
        ),
        agent=sentiment_analyst,
        async_execution=True,
    )

    macro_task = Task(
        description=(
            f"Assess macro impact on {symbol} using your tools. Report: current repo rate, "
            f"CPI trend, USD/INR, GDP growth. Explain how each affects {symbol}'s sector specifically. "
            f"IMPORTANT: Tag every data point with [Source: RBI DBIE]."
        ),
        expected_output=(
            "Macro indicators with sector impact and source citations. "
            "Example: 'Repo rate: 6.5% (unchanged) [Source: RBI DBIE] — "
            "Positive for banking sector (stable NIM)'"
        ),
        agent=macro_analyst,
        async_execution=True,
    )

    # Synthesis task: runs AFTER all parallel tasks complete
    synthesis_task = Task(
        description=(
            f"Synthesize ALL findings for {symbol} into a CrossSourceAnalysis. You MUST:\n"
            f"1. Create a signal for EACH source: price [Angel One/yfinance], "
            f"fundamental [Alpha Vantage/yfinance], sentiment [Finnhub/GNews], macro [RBI DBIE].\n"
            f"2. Each signal needs: source name, signal_type, direction (-1 to +1), confidence (0 to 1), evidence text.\n"
            f"3. DETECT CONTRADICTIONS — e.g. if price is falling but fundamentals are strong, "
            f"or if sentiment is negative but FII holdings increased. State what each source says.\n"
            f"4. In the synthesis narrative, cite EVERY source by name and state what CONFIRMS "
            f"vs what CONTRADICTS. Example: 'Price fell 4% [yfinance] BUT quarterly results show "
            f"8% revenue growth [Alpha Vantage] AND FII holding increased 2% [BSE India]. "
            f"News sentiment is negative due to US recession fears [Finnhub], not company-specific.'\n"
            f"5. Include citations array with source, data_point, value for each key finding.\n"
            f"6. Add disclaimer: 'AI-generated analysis from multiple sources. Not investment advice.'"
        ),
        expected_output=(
            "Complete CrossSourceAnalysis with: symbol, signals (4+ with source names), "
            "contradictions (list of cross-source conflicts), synthesis (narrative citing all sources), "
            "overall_confidence, citations array, and disclaimer."
        ),
        agent=synthesizer,
        output_pydantic=CrossSourceAnalysisOutput,
        context=[collect_task, fundamental_task, sentiment_task, macro_task],
    )

    return Crew(
        agents=[data_collector, fundamental_analyst, sentiment_analyst, macro_analyst, synthesizer],
        tasks=[collect_task, fundamental_task, sentiment_task, macro_task, synthesis_task],
        process=Process.sequential,
        memory=True,
        verbose=False,
        planning=True,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def run_research_crew(symbol: str) -> dict[str, Any]:
    """Execute the full research crew for *symbol* and return structured output."""
    from ..config.settings import settings
    from ..db import research_cache_repo

    if not settings.openai_api_key:
        logger.warning("research_crew.no_api_key")
        return {
            "error": "OPENAI_API_KEY not configured",
            "symbol": symbol,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # Check cache first (TTL = 1 hour)
    cache_key = f"research:{symbol.upper()}"
    cached = await research_cache_repo.get_cached(cache_key)
    if cached is not None:
        logger.info("research_crew.cache_hit", symbol=symbol)
        cached["_cache"] = "hit"
        return cached

    try:
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key
        crew = _build_research_crew(symbol)
        result = await asyncio.to_thread(crew.kickoff)

        if hasattr(result, "pydantic") and result.pydantic:
            output = result.pydantic.model_dump()
        else:
            output = {"raw": str(result), "symbol": symbol}

        # Cache the result
        await research_cache_repo.set_cached(
            cache_key, "research", output, ttl_seconds=3600, symbol=symbol,
        )
        return output

    except Exception as exc:
        logger.error("research_crew.failed", symbol=symbol, error=str(exc))
        return {
            "error": str(exc),
            "symbol": symbol,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
