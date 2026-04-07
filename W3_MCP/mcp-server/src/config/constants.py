"""Centralized constants: TTL values, rate limits, thresholds."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Cache TTL values (seconds)
# ---------------------------------------------------------------------------
TTL_QUOTE_MARKET_HOURS = 30
TTL_QUOTE_AFTER_HOURS = 43_200        # 12 hours
TTL_PRICE_HISTORY = 3_600             # 1 hour — OHLCV bars change slowly
TTL_FUNDAMENTALS = 86_400              # 24 hours
TTL_NEWS = 900                         # 15 minutes
TTL_MF_NAV = 43_200                    # 12 hours
TTL_FILINGS = 0                        # permanent (never expire)
TTL_MACRO = 604_800                    # 7 days
TTL_TECHNICAL_INDICATORS = 21_600      # 6 hours
TTL_SHAREHOLDING = 604_800             # 7 days
TTL_EARNINGS = 86_400                  # 24 hours

TTL_JITTER_PERCENT = 10                # ±10% jitter to prevent stampede

# ---------------------------------------------------------------------------
# Rate limits (per tier, per hour)
# ---------------------------------------------------------------------------
RATE_LIMIT_FREE = 30
RATE_LIMIT_PREMIUM = 150
RATE_LIMIT_ANALYST = 500
RATE_LIMIT_WINDOW_SECONDS = 3600       # 1 hour sliding window

# ---------------------------------------------------------------------------
# Upstream API quotas (daily)
# ---------------------------------------------------------------------------
QUOTA_ALPHA_VANTAGE_DAILY = 25
QUOTA_GNEWS_DAILY = 100
QUOTA_FINNHUB_PER_MINUTE = 60

# ---------------------------------------------------------------------------
# Circuit breaker configuration
# ---------------------------------------------------------------------------
CB_FAILURE_THRESHOLD = 5
CB_FAILURE_WINDOW_SECONDS = 60
CB_RECOVERY_TIMEOUT_SECONDS = 60

# ---------------------------------------------------------------------------
# L1 Cache (in-memory LRU)
# ---------------------------------------------------------------------------
L1_CACHE_MAX_SIZE = 1000

# ---------------------------------------------------------------------------
# Market hours (IST: UTC+5:30)
# ---------------------------------------------------------------------------
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 15
MARKET_CLOSE_HOUR = 15
MARKET_CLOSE_MINUTE = 30

# ---------------------------------------------------------------------------
# Tier names
# ---------------------------------------------------------------------------
TIER_FREE = "free"
TIER_PREMIUM = "premium"
TIER_ANALYST = "analyst"

# ---------------------------------------------------------------------------
# Scopes
# ---------------------------------------------------------------------------
SCOPE_MARKET_READ = "market:read"
SCOPE_FUNDAMENTALS_READ = "fundamentals:read"
SCOPE_TECHNICALS_READ = "technicals:read"
SCOPE_MF_READ = "mf:read"
SCOPE_NEWS_READ = "news:read"
SCOPE_FILINGS_READ = "filings:read"
SCOPE_FILINGS_DEEP = "filings:deep"
SCOPE_MACRO_READ = "macro:read"
SCOPE_MACRO_HISTORICAL = "macro:historical"
SCOPE_RESEARCH_GENERATE = "research:generate"
SCOPE_WATCHLIST_READ = "watchlist:read"
SCOPE_WATCHLIST_WRITE = "watchlist:write"
SCOPE_PORTFOLIO_READ = "portfolio:read"
SCOPE_PORTFOLIO_WRITE = "portfolio:write"

ALL_SCOPES = [
    SCOPE_MARKET_READ, SCOPE_FUNDAMENTALS_READ, SCOPE_TECHNICALS_READ,
    SCOPE_MF_READ, SCOPE_NEWS_READ, SCOPE_FILINGS_READ, SCOPE_FILINGS_DEEP,
    SCOPE_MACRO_READ, SCOPE_MACRO_HISTORICAL, SCOPE_RESEARCH_GENERATE,
    SCOPE_WATCHLIST_READ, SCOPE_WATCHLIST_WRITE,
    SCOPE_PORTFOLIO_READ, SCOPE_PORTFOLIO_WRITE,
]

TIER_SCOPES = {
    TIER_FREE: [
        SCOPE_MARKET_READ, SCOPE_MF_READ, SCOPE_NEWS_READ,
        SCOPE_WATCHLIST_READ, SCOPE_WATCHLIST_WRITE,
    ],
    TIER_PREMIUM: [
        SCOPE_MARKET_READ, SCOPE_MF_READ, SCOPE_NEWS_READ,
        SCOPE_WATCHLIST_READ, SCOPE_WATCHLIST_WRITE,
        SCOPE_FUNDAMENTALS_READ, SCOPE_TECHNICALS_READ,
        SCOPE_MACRO_READ, SCOPE_PORTFOLIO_READ, SCOPE_PORTFOLIO_WRITE,
    ],
    TIER_ANALYST: ALL_SCOPES,
}

# ---------------------------------------------------------------------------
# Rate limits by tier
# ---------------------------------------------------------------------------
TIER_RATE_LIMITS = {
    TIER_FREE: RATE_LIMIT_FREE,
    TIER_PREMIUM: RATE_LIMIT_PREMIUM,
    TIER_ANALYST: RATE_LIMIT_ANALYST,
}

# ---------------------------------------------------------------------------
# Fallback chains per data type
# ---------------------------------------------------------------------------
FALLBACK_CHAIN_PRICE = ["angel_one", "yfinance"]
FALLBACK_CHAIN_FUNDAMENTALS = ["alpha_vantage", "yfinance"]
FALLBACK_CHAIN_NEWS = ["finnhub", "gnews"]
FALLBACK_CHAIN_MF = ["mfapi"]
FALLBACK_CHAIN_FILINGS = ["bse"]
FALLBACK_CHAIN_MACRO = ["rbi_dbie"]
