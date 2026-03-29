"""MCP Prompt Templates — pre-built workflows for common financial analysis tasks."""
from __future__ import annotations

from ..server import mcp


@mcp.prompt()
async def quick_analysis(symbol: str) -> str:
    """Quick stock analysis — suitable for Free tier users."""
    return (
        f"Perform a quick analysis of {symbol} using these steps:\n"
        f"1. Call get_stock_quote for {symbol} to get the current price and daily movement\n"
        f"2. Call get_company_news for {symbol} with days=3 to get recent headlines\n"
        f"3. Provide a 2-3 paragraph summary covering:\n"
        f"   - Current price action (up/down, volume)\n"
        f"   - Key news themes\n"
        f"   - Overall short-term sentiment\n"
        f"Cite each data point with its source."
    )


@mcp.prompt()
async def deep_dive(symbol: str) -> str:
    """Comprehensive deep-dive analysis — Premium tier and above."""
    return (
        f"Perform a comprehensive deep-dive analysis of {symbol}:\n\n"
        f"Step 1: Call get_stock_quote for {symbol}\n"
        f"Step 2: Call get_key_ratios for {symbol}\n"
        f"Step 3: Call get_financial_statements for {symbol}\n"
        f"Step 4: Call get_shareholding_pattern for {symbol}\n"
        f"Step 5: Call get_company_news for {symbol} with days=14\n"
        f"Step 6: Call get_news_sentiment for {symbol}\n"
        f"Step 7: Call get_technical_indicators for {symbol} with indicators=RSI,SMA,MACD\n"
        f"Step 8: Call get_rbi_rates to understand macro context\n\n"
        f"Synthesize all data into a structured report:\n"
        f"- Executive Summary (2-3 sentences)\n"
        f"- Price & Technical Analysis\n"
        f"- Fundamental Analysis (ratios vs sector averages)\n"
        f"- Shareholding Trends (institutional interest)\n"
        f"- News & Sentiment Analysis\n"
        f"- Macro Impact Assessment\n"
        f"- Key Risks & Contradictions\n\n"
        f"Cite EVERY data point with [Source: API name]."
    )


@mcp.prompt()
async def sector_scan(sector: str) -> str:
    """Scan all major stocks in a sector — Premium tier."""
    sector_stocks = {
        "banking": "HDFCBANK,ICICIBANK,SBIN,KOTAKBANK,AXISBANK",
        "it": "TCS,INFY,WIPRO,HCLTECH,TECHM",
        "auto": "MARUTI,TATAMOTORS,BAJAJ-AUTO,EICHERMOT,M&M",
        "pharma": "SUNPHARMA,DRREDDY,CIPLA,DIVISLAB,APOLLOHOSP",
        "fmcg": "HINDUNILVR,ITC,NESTLEIND,BRITANNIA,TATACONSUM",
    }
    symbols = sector_stocks.get(sector.lower(), f"{sector}")
    return (
        f"Perform a sector scan for {sector}:\n\n"
        f"1. For each of these stocks: {symbols}\n"
        f"   - Call get_stock_quote to get current price\n"
        f"   - Call get_key_ratios to get P/E, ROE\n"
        f"2. Call get_market_news with category=business\n"
        f"3. Call get_rbi_rates for macro context\n\n"
        f"Present a table comparing all stocks, then highlight:\n"
        f"- Best value (lowest P/E with good ROE)\n"
        f"- Strongest momentum (biggest recent gain)\n"
        f"- Any sector-wide headwinds from macro/news"
    )


@mcp.prompt()
async def morning_brief() -> str:
    """Morning market brief — Premium tier."""
    return (
        "Generate a morning market brief:\n\n"
        "1. Call get_index_data for NIFTY50 and SENSEX\n"
        "2. Call get_top_gainers_losers for NSE\n"
        "3. Call get_market_news with category=business\n"
        "4. Call get_rbi_rates for macro context\n\n"
        "Format as a concise morning brief:\n"
        "- Market Snapshot (indices, pre-open sentiment)\n"
        "- Top Movers & Why\n"
        "- Key Headlines\n"
        "- Macro Watch (any rate/inflation updates)\n"
        "- What to Watch Today"
    )


@mcp.prompt()
async def morning_risk_brief() -> str:
    """Morning portfolio risk brief — Premium tier."""
    return (
        "Generate a morning risk brief for my portfolio:\n\n"
        "1. Call get_portfolio_summary to see current holdings\n"
        "2. Call portfolio_health_check for concentration alerts\n"
        "3. Call get_market_news for any overnight developments\n"
        "4. Call get_rbi_rates for macro context\n\n"
        "Format as a brief:\n"
        "- Portfolio Value & Overnight Change\n"
        "- Active Risk Alerts\n"
        "- Holdings Affected by Overnight News\n"
        "- Macro Factors to Watch"
    )


@mcp.prompt()
async def rebalance_suggestions() -> str:
    """Portfolio rebalancing suggestions — Premium tier."""
    return (
        "Analyze my portfolio and suggest rebalancing:\n\n"
        "1. Call get_portfolio_summary for current allocation\n"
        "2. Call check_concentration_risk for flags\n"
        "3. Call check_mf_overlap for mutual fund overlap\n\n"
        "Provide rebalancing suggestions:\n"
        "- Over-concentrated positions to reduce\n"
        "- Under-represented sectors to add\n"
        "- Overlap concerns with mutual funds\n"
        "IMPORTANT: Do NOT give buy/sell advice — only highlight imbalances."
    )


@mcp.prompt()
async def earnings_exposure() -> str:
    """Portfolio earnings exposure check — Premium tier."""
    return (
        "Check which portfolio holdings have upcoming earnings:\n\n"
        "1. Call get_portfolio_summary for current holdings\n"
        "2. Call get_earnings_calendar for upcoming 4 weeks\n"
        "3. For each overlap, call get_pre_earnings_profile\n\n"
        "Present:\n"
        "- Timeline: Which holdings report when\n"
        "- Risk Assessment: Concentration in reporting stocks\n"
        "- Preview: Key metrics to watch for each"
    )


@mcp.prompt()
async def earnings_preview(symbol: str) -> str:
    """Pre-earnings analysis for a specific company — Premium tier."""
    return (
        f"Generate a pre-earnings preview for {symbol}:\n\n"
        f"1. Call get_pre_earnings_profile for {symbol}\n"
        f"2. Call get_eps_history for {symbol} with quarters=8\n"
        f"3. Call get_analyst_expectations for {symbol}\n"
        f"4. Call get_news_sentiment for {symbol}\n\n"
        f"Present:\n"
        f"- Earnings Track Record (beat/miss history)\n"
        f"- Consensus Expectations vs Historical Trend\n"
        f"- Sentiment Going Into Results\n"
        f"- Key Metrics to Watch\n"
        f"- Historical Post-Results Price Reaction Pattern"
    )


@mcp.prompt()
async def results_flash(symbol: str) -> str:
    """Post-earnings quick verdict — Premium tier."""
    return (
        f"Generate a results flash for {symbol}:\n\n"
        f"1. Call compare_actual_vs_expected for {symbol}\n"
        f"2. Call get_post_results_reaction for {symbol}\n"
        f"3. Call get_company_news for {symbol} with days=2\n\n"
        f"Present a quick verdict:\n"
        f"- Beat/Miss/Inline with surprise magnitude\n"
        f"- Price Reaction (day 0, day 1)\n"
        f"- Market Narrative (why the stock moved)\n"
        f"Keep it concise — 3-4 key bullet points."
    )


@mcp.prompt()
async def sector_earnings_recap(sector: str) -> str:
    """Full sector earnings season recap — Analyst tier."""
    return (
        f"Generate a sector earnings recap for {sector}:\n\n"
        f"1. Call earnings_season_dashboard\n"
        f"2. For top companies in {sector}, call compare_quarterly_performance\n"
        f"3. Call get_market_news for {sector} context\n\n"
        f"Present:\n"
        f"- Sector Scorecard: beats vs misses\n"
        f"- Revenue & Profit Trends\n"
        f"- Standout Performers & Disappointments\n"
        f"- Sector Outlook Based on This Season's Results"
    )


@mcp.prompt()
async def earnings_surprise_scan() -> str:
    """Scan for biggest earnings surprises — Analyst tier."""
    return (
        "Scan for the biggest earnings surprises this season:\n\n"
        "1. Call earnings_season_dashboard for recent results\n"
        "2. For top 5 surprises, call cross_reference_signals\n\n"
        "Present:\n"
        "- Top Positive Surprises (biggest beats)\n"
        "- Top Negative Surprises (biggest misses)\n"
        "- Cross-Source Signals: What other data confirms/contradicts\n"
        "- Potential Trading Implications (NOT advice)"
    )
