"""PS2 Risk Crew — 4-agent sequential pipeline for portfolio risk analysis."""
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


class PortfolioQuoteTool(BaseTool):
    name: str = "get_portfolio_quotes"
    description: str = "Get current quotes for a list of portfolio symbols."

    def _run(self, symbols: str) -> str:
        from ..data_facade.facade import data_facade
        sym_list = [s.strip() for s in symbols.split(",")]
        results = {}
        for s in sym_list:
            data = _run_async(data_facade.get_price(s))
            results[s] = {"ltp": data.get("ltp"), "change_pct": data.get("change_pct")}
        return json.dumps(results, default=str)


class MacroContextTool(BaseTool):
    name: str = "get_macro_context"
    description: str = "Get RBI macro indicators for risk assessment."

    def _run(self, **kwargs: Any) -> str:
        from ..data_facade.facade import data_facade
        result = _run_async(data_facade.get_macro())
        return json.dumps(result, default=str)


class SentimentScanTool(BaseTool):
    name: str = "scan_sentiment"
    description: str = "Get news sentiment for a stock symbol."

    def _run(self, symbol: str) -> str:
        from ..data_facade.facade import data_facade
        result = _run_async(data_facade.get_news(symbol, days=7))
        return json.dumps(result, default=str)


# ---------------------------------------------------------------------------
# Output model
# ---------------------------------------------------------------------------

class RiskAlertOutput(BaseModel):
    alert_type: str
    severity: str
    message: str


class RiskSignalOutput(BaseModel):
    source: str
    signal_type: str
    direction: float = Field(ge=-1.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str
    timestamp: str = ""


class RiskCitationOutput(BaseModel):
    source: str
    data_point: str
    value: str = ""
    timestamp: str = ""


class PortfolioRiskReportOutput(BaseModel):
    user_id: str = "demo"
    risk_score: float = Field(default=50.0, ge=0.0, le=100.0)
    signals: list[RiskSignalOutput] = []
    alerts: list[RiskAlertOutput] = []
    contradictions: list[str] = []
    narrative: str = ""
    citations: list[RiskCitationOutput] = []
    recommendations: list[str] = []
    disclaimer: str = "AI-generated risk analysis. Not investment advice."


# ---------------------------------------------------------------------------
# Crew builder
# ---------------------------------------------------------------------------

def _build_risk_crew(holdings: list[dict[str, Any]], user_id: str) -> Crew:
    from ..config.settings import settings

    llm_fast = f"openai/{settings.openai_model_fast}"
    llm_reasoning = f"openai/{settings.openai_model_reasoning}"
    symbols_str = ",".join(h.get("symbol", "") for h in holdings)

    scanner = Agent(
        role="Portfolio Scanner",
        goal="Fetch current prices and calculate P&L for all holdings",
        backstory="Scans every holding for current market price and unrealised P&L.",
        llm=llm_fast,
        tools=[PortfolioQuoteTool()],
        memory=True, max_iter=8, allow_delegation=False, verbose=False,
    )

    risk_detector = Agent(
        role="Risk Detector",
        goal="Identify concentration risk, sector tilt, and sentiment divergence",
        backstory="Flags holdings exceeding 20% weight, sectors exceeding 40%, and sentiment shifts.",
        llm=llm_reasoning,
        tools=[SentimentScanTool()],
        memory=True, max_iter=8, allow_delegation=False, verbose=False,
    )

    macro_mapper = Agent(
        role="Macro Mapper",
        goal="Map RBI rates, inflation, and forex to portfolio-level impact",
        backstory="Connects macro indicators to sector-level portfolio risk.",
        llm=llm_reasoning,
        tools=[MacroContextTool()],
        memory=True, max_iter=8, allow_delegation=False, verbose=False,
    )

    narrator = Agent(
        role="Risk Narrator",
        goal="Produce a structured PortfolioRiskReport with citations",
        backstory="Synthesises scanner, risk, and macro outputs into a risk narrative.",
        llm=llm_reasoning,
        memory=True, max_iter=10, allow_delegation=False, verbose=False,
    )

    scan_task = Task(
        description=f"Fetch current prices for: {symbols_str}. Calculate P&L for each.",
        expected_output="JSON with per-stock current prices and P&L.",
        agent=scanner,
    )

    risk_task = Task(
        description="Check concentration risk (>20% single stock, >40% sector). Check news sentiment for top holdings.",
        expected_output="JSON with risk flags and sentiment scores.",
        agent=risk_detector,
    )

    macro_task = Task(
        description="Get macro data and assess how repo rate, CPI, USD/INR affect this portfolio.",
        expected_output="JSON with macro impacts per sector.",
        agent=macro_mapper,
    )

    narrative_task = Task(
        description=f"Synthesise all findings into a PortfolioRiskReport for user {user_id}.",
        expected_output="Complete PortfolioRiskReport with alerts, narrative, citations.",
        agent=narrator,
        output_pydantic=PortfolioRiskReportOutput,
    )

    return Crew(
        agents=[scanner, risk_detector, macro_mapper, narrator],
        tasks=[scan_task, risk_task, macro_task, narrative_task],
        process=Process.sequential,
        memory=True, verbose=False,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def run_risk_crew(holdings: list[dict[str, Any]], user_id: str = "demo") -> dict[str, Any]:
    """Execute the risk crew and return a structured risk report."""
    from ..config.settings import settings

    if not settings.openai_api_key:
        return {"error": "OPENAI_API_KEY not configured", "user_id": user_id}

    if not holdings:
        return {"error": "No holdings to analyse", "user_id": user_id}

    try:
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key
        crew = _build_risk_crew(holdings, user_id)
        result = await asyncio.to_thread(crew.kickoff)

        if hasattr(result, "pydantic") and result.pydantic:
            return result.pydantic.model_dump()
        return {"raw": str(result), "user_id": user_id}

    except Exception as exc:
        logger.error("risk_crew.failed", user_id=user_id, error=str(exc))
        return {"error": str(exc), "user_id": user_id}
