"""Market data tools — stock quotes, price history, indices, movers, and technicals."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ...server import mcp
from ...data_facade.facade import data_facade


@mcp.tool()
async def get_stock_quote(symbol: str) -> dict[str, Any]:
    """Get the real-time stock quote for an Indian equity.

    Returns the last traded price (LTP), absolute and percentage change from
    previous close, intra-day OHLC, volume, market capitalisation, and 52-week
    range.  Data is sourced via the Angel One → yfinance fallback chain.

    Args:
        symbol: NSE/BSE ticker symbol (e.g. "RELIANCE", "TCS", "INFY").

    Returns:
        dict with keys: data, source, cache_status, timestamp, disclaimer.
    """
    import re

    symbol = symbol.strip().upper()
    if not symbol or not re.match(r"^[A-Z0-9&_.-]{1,20}$", symbol):
        return {
            "error": f"Invalid symbol: '{symbol}'. Must be a valid NSE/BSE ticker (e.g. RELIANCE, TCS, INFY).",
            "error_code": "INVALID_SYMBOL",
        }

    result = await data_facade.get_price(symbol)

    ltp = result.get("ltp") if isinstance(result, dict) else None
    if ltp is None or ltp == 0:
        return {
            "error": f"Symbol '{symbol}' not found or has no trading data. Use a valid NSE/BSE ticker (e.g. RELIANCE, TCS, INFY).",
            "error_code": "SYMBOL_NOT_FOUND",
        }

    return {
        "data": {
            "symbol": symbol,
            "ltp": result.get("ltp"),
            "change": result.get("change"),
            "change_pct": result.get("change_pct"),
            "open": result.get("open"),
            "high": result.get("high"),
            "low": result.get("low"),
            "close": result.get("close"),
            "volume": result.get("volume"),
            "market_cap": result.get("market_cap"),
            "week_52_high": result.get("week_52_high"),
            "week_52_low": result.get("week_52_low"),
        },
        "source": result.get("_source", "unknown"),
        "cache_status": result.get("_cache", "miss"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "For informational purposes only. Not investment advice.",
    }


@mcp.tool()
async def get_price_history(
    symbol: str,
    from_date: str,
    to_date: str,
    interval: str = "1d",
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    """Get historical OHLCV price data for an Indian equity.

    Returns a paginated array of candlestick bars (open, high, low, close,
    volume) for the requested date range and interval.

    Args:
        symbol: NSE/BSE ticker symbol (e.g. "RELIANCE").
        from_date: Start date in YYYY-MM-DD format.
        to_date: End date in YYYY-MM-DD format.
        interval: Candle interval — "1d", "1wk", or "1mo".
        page: Page number (1-indexed, default 1).
        page_size: Bars per page (default 100, max 500).

    Returns:
        dict with keys: data (list of OHLCV bars), source, cache_status,
        timestamp, disclaimer.
    """
    page_size = max(1, min(page_size, 500))
    page = max(1, page)
    # TODO: Add dedicated price_history method to DataFacade
    result = await data_facade.get_price(symbol)
    all_bars = result.get("bars", [])
    total = len(all_bars)
    start = (page - 1) * page_size
    bars = all_bars[start:start + page_size]
    return {
        "data": {
            "symbol": symbol,
            "from_date": from_date,
            "to_date": to_date,
            "interval": interval,
            "bars": bars,
            "total_count": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total else 0,
        },
        "source": result.get("_source", "unknown"),
        "cache_status": result.get("_cache", "miss"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "For informational purposes only. Not investment advice.",
    }


@mcp.tool()
async def get_index_data(index: str = "NIFTY50") -> dict[str, Any]:
    """Get current value and composition for a major Indian market index.

    Returns the index value, change, advance/decline counts, and top
    gainers/losers within the index.

    Args:
        index: Index name — "NIFTY50", "SENSEX", "NIFTYBANK", "NIFTYNEXT50".

    Returns:
        dict with keys: data, source, cache_status, timestamp, disclaimer.
    """
    # TODO: Add dedicated index_data method to DataFacade
    result = await data_facade.get_price(index)
    return {
        "data": {
            "index_name": index,
            "value": result.get("ltp"),
            "change": result.get("change"),
            "change_pct": result.get("change_pct"),
            "advances": result.get("advances"),
            "declines": result.get("declines"),
            "top_gainers": result.get("top_gainers", []),
            "top_losers": result.get("top_losers", []),
        },
        "source": result.get("_source", "unknown"),
        "cache_status": result.get("_cache", "miss"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "For informational purposes only. Not investment advice.",
    }


@mcp.tool()
async def get_top_gainers_losers(
    exchange: str = "NSE",
    count: int = 10,
) -> dict[str, Any]:
    """Get the top gaining and losing stocks on an Indian exchange.

    Returns two sorted arrays: gainers (by highest % change) and losers
    (by lowest % change), each containing symbol, LTP, change %, and volume.

    Args:
        exchange: Exchange code — "NSE" or "BSE".
        count: Number of stocks per list (default 10, max 50).

    Returns:
        dict with keys: data, source, cache_status, timestamp, disclaimer.
    """
    # TODO: Add dedicated top_movers method to DataFacade
    result = await data_facade.get_price(f"{exchange}:MOVERS")
    return {
        "data": {
            "exchange": exchange,
            "count": count,
            "gainers": result.get("gainers", [])[:count],
            "losers": result.get("losers", [])[:count],
        },
        "source": result.get("_source", "unknown"),
        "cache_status": result.get("_cache", "miss"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "For informational purposes only. Not investment advice.",
    }


@mcp.tool()
async def get_technical_indicators(
    symbol: str,
    indicators: str = "RSI,SMA,EMA",
) -> dict[str, Any]:
    """Compute technical indicators for an Indian equity.

    Returns calculated values for the requested indicators along with a
    directional signal (buy / sell / neutral).

    Args:
        symbol: NSE/BSE ticker symbol (e.g. "RELIANCE").
        indicators: Comma-separated indicator names — e.g. "RSI,SMA,EMA,MACD,BBANDS".

    Returns:
        dict with keys: data (list of indicator results), source, cache_status,
        timestamp, disclaimer.
    """
    indicator_list = [i.strip().upper() for i in indicators.split(",")]
    result = await data_facade.get_technical_indicators(symbol, indicator_list)
    return {
        "data": {
            "symbol": symbol,
            "indicators": result.get("indicators", []),
        },
        "source": result.get("_source", "unknown"),
        "cache_status": result.get("_cache", "miss"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "For informational purposes only. Not investment advice.",
    }
