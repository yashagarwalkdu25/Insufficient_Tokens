"""PS3 Earnings Crew — 4-agent parallel pipeline for earnings analysis.

Architecture: fetch_task + reaction_task run IN PARALLEL (async_execution=True),
then parse_task runs with fetch_task context, then verdict_task synthesises all."""
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

os.environ.setdefault("LANGCHAIN_TRACING_V2", os.environ.get("LANGCHAIN_TRACING_V2", "false"))


# ---------------------------------------------------------------------------
# Custom Tools
# ---------------------------------------------------------------------------

def _run_async(coro):
    """Run an async coroutine from CrewAI's sync thread pool."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class FilingTool(BaseTool):
    name: str = "get_bse_filings"
    description: str = "Get recent BSE corporate filings/results for a company."

    def _run(self, symbol: str) -> str:
        from ..data_facade.facade import data_facade
        result = _run_async(data_facade.get_filings(symbol, "results"))
        return json.dumps(result, default=str)


class PriceReactionTool(BaseTool):
    name: str = "get_price_reaction"
    description: str = "Get stock price and recent change for post-results reaction analysis."

    def _run(self, symbol: str) -> str:
        from ..data_facade.facade import data_facade
        result = _run_async(data_facade.get_price(symbol))
        return json.dumps(result, default=str)


class EarningsNewsTool(BaseTool):
    name: str = "get_earnings_news"
    description: str = "Get news around earnings announcement for sentiment context."

    def _run(self, symbol: str) -> str:
        from ..data_facade.facade import data_facade
        result = _run_async(data_facade.get_news(symbol, days=3))
        return json.dumps(result, default=str)


class FundamentalsTool(BaseTool):
    name: str = "get_company_fundamentals"
    description: str = "Get fundamental data (EPS, revenue, ratios) for earnings comparison."

    def _run(self, symbol: str) -> str:
        from ..data_facade.facade import data_facade
        result = _run_async(data_facade.get_fundamentals(symbol))
        return json.dumps(result, default=str)


# ---------------------------------------------------------------------------
# Output model
# ---------------------------------------------------------------------------

class EarningsSignalOutput(BaseModel):
    source: str
    signal_type: str
    direction: float = Field(ge=-1.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str
    timestamp: str = ""


class EarningsCitationOutput(BaseModel):
    source: str
    data_point: str
    value: str = ""
    timestamp: str = ""


class EarningsVerdictOutput(BaseModel):
    symbol: str
    quarter: str = ""
    beat_miss: str = "inline"
    signals: list[EarningsSignalOutput] = []
    filing_highlights: dict[str, Any] = {}
    market_reaction: dict[str, Any] = {}
    contradictions: list[str] = []
    narrative: str = ""
    citations: list[EarningsCitationOutput] = []
    disclaimer: str = "AI-generated earnings analysis. Not investment advice."


# ---------------------------------------------------------------------------
# Crew builder
# ---------------------------------------------------------------------------

def _build_earnings_crew(symbol: str, quarter: str) -> Crew:
    from ..config.settings import settings

    llm_fast = f"openai/{settings.openai_model_fast}"
    llm_reasoning = f"openai/{settings.openai_model_reasoning}"

    filing_fetcher = Agent(
        role="Filing Fetcher",
        goal=f"Retrieve the BSE quarterly filing for {symbol}",
        backstory="Specialises in locating and retrieving BSE corporate filings.",
        llm=llm_fast,
        tools=[FilingTool()],
        memory=True, max_iter=8, allow_delegation=False, verbose=False,
    )

    filing_parser = Agent(
        role="Filing Parser",
        goal=f"Extract revenue, PAT, EPS, and margins from {symbol}'s filing",
        backstory="Extracts structured financial data from unstructured BSE filings using LLM reasoning.",
        llm=llm_reasoning,
        tools=[FundamentalsTool()],
        memory=True, max_iter=8, allow_delegation=False, verbose=False,
    )

    market_reactor = Agent(
        role="Market Reactor",
        goal=f"Analyse price reaction to {symbol}'s results",
        backstory="Tracks price changes on result day and following 2 days, volume spikes, and options activity.",
        llm=llm_fast,
        tools=[PriceReactionTool(), EarningsNewsTool()],
        memory=True, max_iter=8, allow_delegation=False, verbose=False,
    )

    narrator = Agent(
        role="Earnings Narrator",
        goal=f"Produce a structured EarningsVerdict for {symbol}",
        backstory=(
            "Synthesises filing data, price reaction, and news into a comprehensive "
            "earnings verdict. Detects contradictions and assigns confidence."
        ),
        llm=llm_reasoning,
        memory=True, max_iter=10, allow_delegation=False, verbose=False,
    )

    # Tasks — fetch_task + reaction_task run IN PARALLEL
    fetch_task = Task(
        description=f"Get the latest BSE quarterly result filing for {symbol}.",
        expected_output="JSON with filing metadata and key financial figures.",
        agent=filing_fetcher,
        async_execution=True,
    )

    reaction_task = Task(
        description=f"Get {symbol}'s stock price reaction around the result date and recent news.",
        expected_output="JSON with price changes day 0/1/2 and news sentiment.",
        agent=market_reactor,
        async_execution=True,
    )

    # parse_task depends on fetch_task output
    parse_task = Task(
        description=f"Extract revenue, net profit (PAT), EPS, and operating margin from {symbol}'s filing.",
        expected_output="JSON with structured financial data.",
        agent=filing_parser,
        context=[fetch_task],
    )

    # Verdict task: runs AFTER all tasks complete
    verdict_task = Task(
        description=(
            f"Synthesise all findings into an EarningsVerdict for {symbol} {quarter}. "
            f"Determine beat/miss/inline. Detect contradictions. Cite all sources."
        ),
        expected_output="Complete EarningsVerdict with narrative and citations.",
        agent=narrator,
        output_pydantic=EarningsVerdictOutput,
        context=[fetch_task, parse_task, reaction_task],
    )

    return Crew(
        agents=[filing_fetcher, filing_parser, market_reactor, narrator],
        tasks=[fetch_task, reaction_task, parse_task, verdict_task],
        process=Process.sequential,
        memory=True, verbose=False,
        planning=True,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def run_earnings_crew(symbol: str, quarter: str = "") -> dict[str, Any]:
    """Execute the earnings crew and return a structured verdict."""
    from ..config.settings import settings
    from ..db import research_cache_repo

    if not settings.openai_api_key:
        return {"error": "OPENAI_API_KEY not configured", "symbol": symbol}

    # Check cache (TTL = 1 hour)
    q = quarter or "latest"
    cache_key = f"earnings:{symbol.upper()}:{q}"
    cached = await research_cache_repo.get_cached(cache_key)
    if cached is not None:
        logger.info("earnings_crew.cache_hit", symbol=symbol)
        cached["_cache"] = "hit"
        return cached

    try:
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key
        crew = _build_earnings_crew(symbol, q)
        result = await asyncio.to_thread(crew.kickoff)

        if hasattr(result, "pydantic") and result.pydantic:
            output = result.pydantic.model_dump()
        else:
            output = {"raw": str(result), "symbol": symbol}

        await research_cache_repo.set_cached(
            cache_key, "earnings", output, ttl_seconds=3600, symbol=symbol,
        )
        return output

    except Exception as exc:
        logger.error("earnings_crew.failed", symbol=symbol, error=str(exc))
        return {"error": str(exc), "symbol": symbol}
