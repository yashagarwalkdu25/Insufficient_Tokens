"""Auth middleware: scope enforcement and tier-based tool filtering."""

from __future__ import annotations

from typing import Any, TypeAlias

import structlog

from .provider import KeycloakAuthProvider, TokenClaims
from ..config.constants import (
    SCOPE_MARKET_READ,
    SCOPE_FUNDAMENTALS_READ,
    SCOPE_TECHNICALS_READ,
    SCOPE_MF_READ,
    SCOPE_NEWS_READ,
    SCOPE_FILINGS_READ,
    SCOPE_FILINGS_DEEP,
    SCOPE_MACRO_READ,
    SCOPE_MACRO_HISTORICAL,
    SCOPE_RESEARCH_GENERATE,
    SCOPE_WATCHLIST_READ,
    SCOPE_WATCHLIST_WRITE,
    SCOPE_PORTFOLIO_READ,
    SCOPE_PORTFOLIO_WRITE,
)

logger = structlog.get_logger(__name__)

ToolScopeSpec: TypeAlias = str | tuple[str, ...]

# ---------------------------------------------------------------------------
# Tool -> required scope(s): tuple = ALL must be present (PDF MF comparison = Premium+)
# ---------------------------------------------------------------------------
TOOL_SCOPE_MAP: dict[str, ToolScopeSpec] = {
    # -- Free-tier tools ---------------------------------------------------
    "get_stock_quote": SCOPE_MARKET_READ,
    "get_price_history": SCOPE_MARKET_READ,
    "get_index_data": SCOPE_MARKET_READ,
    "get_top_gainers_losers": SCOPE_MARKET_READ,
    "search_mutual_funds": SCOPE_MF_READ,
    "get_fund_nav": SCOPE_MF_READ,
    "get_company_news": SCOPE_NEWS_READ,
    "get_market_news": SCOPE_NEWS_READ,
    "get_earnings_calendar": SCOPE_MARKET_READ,
    "get_past_results_dates": SCOPE_MARKET_READ,
    "add_to_portfolio": SCOPE_WATCHLIST_WRITE,
    "remove_from_portfolio": SCOPE_WATCHLIST_WRITE,
    "import_portfolio": SCOPE_WATCHLIST_WRITE,
    "get_portfolio_summary": SCOPE_WATCHLIST_READ,
    "portfolio_health_check": SCOPE_PORTFOLIO_READ,
    "check_concentration_risk": SCOPE_PORTFOLIO_READ,
    # -- Premium-tier tools ------------------------------------------------
    "get_financial_statements": SCOPE_FUNDAMENTALS_READ,
    "get_key_ratios": SCOPE_FUNDAMENTALS_READ,
    "get_shareholding_pattern": SCOPE_FUNDAMENTALS_READ,
    "get_quarterly_results": SCOPE_FUNDAMENTALS_READ,
    "get_technical_indicators": SCOPE_TECHNICALS_READ,
    "get_news_sentiment": SCOPE_NEWS_READ,
    "get_rbi_rates": SCOPE_MACRO_READ,
    "get_inflation_data": SCOPE_MACRO_HISTORICAL,
    "compare_funds": (SCOPE_MF_READ, SCOPE_FUNDAMENTALS_READ),
    "get_corporate_filings": SCOPE_FILINGS_READ,
    "check_mf_overlap": SCOPE_PORTFOLIO_READ,
    "check_macro_sensitivity": SCOPE_PORTFOLIO_READ,
    "detect_sentiment_shift": SCOPE_PORTFOLIO_READ,
    "get_eps_history": SCOPE_FUNDAMENTALS_READ,
    "get_pre_earnings_profile": SCOPE_FUNDAMENTALS_READ,
    "get_analyst_expectations": SCOPE_FUNDAMENTALS_READ,
    "get_post_results_reaction": SCOPE_FUNDAMENTALS_READ,
    "compare_actual_vs_expected": SCOPE_FUNDAMENTALS_READ,
    "get_option_chain": SCOPE_FUNDAMENTALS_READ,
    # -- Analyst-tier tools ------------------------------------------------
    "cross_reference_signals": SCOPE_RESEARCH_GENERATE,
    "generate_research_brief": SCOPE_RESEARCH_GENERATE,
    "compare_companies": SCOPE_RESEARCH_GENERATE,
    "portfolio_risk_report": SCOPE_RESEARCH_GENERATE,
    "what_if_analysis": SCOPE_RESEARCH_GENERATE,
    "get_filing_document": SCOPE_FILINGS_DEEP,
    "parse_quarterly_filing": SCOPE_FILINGS_DEEP,
    "earnings_verdict": SCOPE_RESEARCH_GENERATE,
    "earnings_season_dashboard": SCOPE_RESEARCH_GENERATE,
    "compare_quarterly_performance": SCOPE_RESEARCH_GENERATE,
    # -- Alert & Notification tools ----------------------------------------
    "create_price_alert": SCOPE_WATCHLIST_WRITE,
    "create_portfolio_risk_alert": SCOPE_PORTFOLIO_READ,
    "create_sentiment_alert": SCOPE_PORTFOLIO_READ,
    "create_earnings_reminder": SCOPE_WATCHLIST_WRITE,
    "get_my_alerts": SCOPE_WATCHLIST_READ,
    "delete_alert": SCOPE_WATCHLIST_WRITE,
    "get_notifications": SCOPE_WATCHLIST_READ,
    "mark_notifications_read": SCOPE_WATCHLIST_WRITE,
    "check_and_trigger_alerts": SCOPE_PORTFOLIO_READ,
    # -- Morning brief & advanced tools ------------------------------------
    "generate_morning_brief": SCOPE_PORTFOLIO_READ,
    # -- Resource subscription tools ---------------------------------------
    "subscribe_resource": SCOPE_WATCHLIST_WRITE,
    "unsubscribe_resource": SCOPE_WATCHLIST_WRITE,
    "get_subscribed_updates": SCOPE_WATCHLIST_READ,
}


def check_scope(required_scope: str, user_claims: TokenClaims) -> bool:
    """Return True if the user's claims include the required scope."""
    return required_scope in user_claims.scopes


def tool_scope_specs(tool_name: str) -> tuple[str, ...]:
    """Normalise TOOL_SCOPE_MAP entry to a tuple of required scopes."""
    spec = TOOL_SCOPE_MAP.get(tool_name)
    if spec is None:
        return ()
    if isinstance(spec, str):
        return (spec,)
    return tuple(spec)


def user_has_tool_scopes(tool_name: str, user_claims: TokenClaims) -> bool:
    """True if the user holds every scope required for the tool."""
    return all(s in user_claims.scopes for s in tool_scope_specs(tool_name))


async def get_user_tier(token: str) -> str:
    """Decode a token and return the user's tier string."""
    provider = KeycloakAuthProvider()
    claims = await provider.validate_token(token)
    return claims.tier


class TierToolFilter:
    """Filters the MCP ``tools/list`` response based on user scopes.

    Only tools whose required scope is present in the user's claims are
    returned, so lower-tier users never see tools they cannot call.
    """

    def filter_tools(
        self,
        tools: list[dict[str, Any]],
        user_claims: TokenClaims,
    ) -> list[dict[str, Any]]:
        """Return the subset of *tools* the user is authorised to invoke."""
        allowed: list[dict[str, Any]] = []
        for tool in tools:
            tool_name: str = tool.get("name", "")
            reqs = tool_scope_specs(tool_name)
            if not reqs:
                logger.warning("tool_scope_unmapped", tool=tool_name)
                continue
            if user_has_tool_scopes(tool_name, user_claims):
                allowed.append(tool)
            else:
                logger.debug(
                    "tool_filtered",
                    tool=tool_name,
                    required=reqs,
                    tier=user_claims.tier,
                )
        return allowed

    def is_tool_allowed(self, tool_name: str, user_claims: TokenClaims) -> bool:
        """Check whether a single tool invocation is permitted."""
        if not tool_scope_specs(tool_name):
            logger.warning("tool_scope_unmapped", tool=tool_name)
            return False
        return user_has_tool_scopes(tool_name, user_claims)
