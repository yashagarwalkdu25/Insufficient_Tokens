# Indian Financial Data Sources: The Honest Guide

**Every data source listed in the hackathon brief has real-world catches.** This document gives you the unvarnished truth — what works, what breaks, what's legal, and what will get you blocked — for each API you'll need to build the MCP server.

---

## Source 1: NSE India (via `stock-nse-india` npm / direct scraping)

**What it provides:** Live quotes, indices, F&O data, historical OHLCV, option chains, top gainers/losers, shareholding patterns, bulk/block deals.

**The truth: This is NOT a public API.** NSE does not offer an official free REST API. Every library — `stock-nse-india` (npm), `nsemine` (Python), `nse` (Python), `jugaad_data`, `NseIndiaApi` — works by reverse-engineering NSE's internal website endpoints (e.g., `https://www.nseindia.com/api/quote-equity?symbol=RELIANCE`). These endpoints power nseindia.com's frontend and are undocumented.

### Rate limits
- NSE throttles at roughly **3 requests per second** from a single IP
- Requires browser-like headers (`User-Agent`, cookies) — requests without proper session cookies return 403
- NSE periodically changes endpoint URLs (the 2020 DNS migration to `www1.nseindia.com` broke every scraper overnight)
- Libraries like `nsemine` include built-in caching and anti-scraper evasion specifically because of how aggressive NSE's blocking is

### Legal status
- Scraping real-time NSE data from third-party sites is legally and contractually risky and usually violates terms of service. The correct approach is to license real-time data from authorized sources or use NSE-approved feeds
- NSE's TOS (Section 22.f) explicitly prohibits automated data extraction
- Exchanges require licensing for redistributing their real-time data; using scraped data for public display or commercial use can violate exchange market data policies and incur fines
- For a production startup, this is a **legal liability** — fine for hackathon demos, dangerous for production

### Advantages
- Richest source of Indian equity data available without payment
- Covers everything: live prices, option chains, FII/DII data, delivery volumes, pre-open market data, index composition
- Multiple maintained Python/Node libraries (nsemine updated Feb 2026, nse package updated Jan 2026)

### Limitations
- **No official API, no SLA, no guarantee of uptime or data accuracy**
- Endpoint changes can break your entire system with zero notice
- IP blocking during heavy usage, especially during market hours
- Not suitable for commercial redistribution without NSE data vendor licensing (starts at ₹3+ lakhs/year)

### Recommendation for MCP server
Use as a **secondary/enrichment source only**. Primary market data should come from broker APIs (Angel One, Zerodha). Cache aggressively (60s for prices, 24h for fundamentals). Implement circuit breakers. Never make this your sole source for any data type.

---

## Source 2: yfinance (`.NS` / `.BO` tickers)

**What it provides:** Historical prices, dividends, splits, financials (income statement, balance sheet, cash flow), company info, analyst recommendations.

**The truth: yfinance is in a reliability crisis.** It is not an official API — it scrapes Yahoo Finance endpoints and HTML pages. Yahoo sees many rapid requests from the same IP and starts rate-limiting or even temporarily banning those requests. The situation deteriorated sharply in late 2024.

### Rate limits
- One user reported pulling data for 7,000 stocks daily for a year without issues until November 2024, when Yahoo started cracking down — now rate-limited after ~950 tickers
- Yahoo's documented limit is approximately **360 requests per hour**, but enforcement is inconsistent and sometimes stricter
- Users report getting rate-limited with as few as 4-5 requests per day during Yahoo's periodic crackdowns
- Rate limit blocks can persist for over 24 hours, with some users reporting blocks lasting weeks
- Even trying to download a single stock sometimes doesn't work — blocks can persist for weeks
- VPNs and proxy rotation help but aren't a reliable fix — Yahoo sometimes blocks by request pattern, not just IP

### Legal status
- yfinance is **unofficial and may violate Yahoo's ToS** for automated data collection
- yfinance works by mimicking browser or API calls to Yahoo. Because this is unofficial and fragile, any change on Yahoo's site can break yfinance
- Not suitable for commercial use — Yahoo has no licensing agreement for programmatic data access at scale

### Advantages
- When it works, provides excellent Indian stock data: historical prices, full financial statements, balance sheets, cash flow statements, analyst estimates
- India coverage via `.NS` (NSE) and `.BO` (BSE) ticker suffixes is quite good
- Returns pandas DataFrames, easy to work with in Python
- Covers dividends, splits, corporate actions automatically adjusted in historical data

### Limitations
- **Unreliable for production use** — can break any day without warning
- yfinance is fine for occasional lookup or small backtests, but unreliable for continuous data collection
- Financial statement data for Indian companies is sometimes incomplete or delayed vs. BSE filings
- Company `.info` endpoint (P/E, market cap, etc.) is the most frequently blocked endpoint

### Recommendation for MCP server
Use as a **fallback source only**, never as primary. Implement `yfinance-cache` (maintained by ValueRaider) to minimize requests. Add exponential backoff and graceful degradation. Pre-cache all Nifty 50/Nifty 500 fundamentals during off-peak hours. Have broker APIs or Alpha Vantage as the primary source, with yfinance as enrichment when available.

---

## Source 3: MFapi.in

**What it provides:** Mutual fund NAV history, scheme search, fund house data for all AMFI-registered schemes.

**The truth: This is the single most reliable free Indian financial API.** It sources data directly from AMFI (Association of Mutual Funds in India), which is the authoritative body. Historical NAV data, scheme information, and daily updates for all Indian mutual funds.

### Rate limits
- The API implements rate limiting to ensure fair usage, but limits are generous and undocumented — in practice, reasonable usage (hundreds of requests/day) works fine
- No API key required — completely open access
- The service maintains a status page for real-time uptime monitoring

### Legal status
- Fully legitimate — sources from AMFI's public data (the official `NAVAll.txt` file that AMFI publishes daily)
- No ToS restrictions on programmatic access
- Safe for commercial use

### Advantages
- **Free, no authentication, no API key** — just call the endpoints
- Covers all ~10,000+ AMFI-registered mutual fund schemes in India
- Full historical NAV data going back years
- Clean JSON responses with scheme metadata (fund house, category, ISIN, scheme type)
- Now available as an MCP service, delivering the complete history of Indian mutual funds, refreshed daily
- Swagger UI documentation with interactive testing

### Limitations
- Only provides NAV data — no holdings composition, expense ratios, or portfolio breakdown
- NAV updates are end-of-day (typically available by 11 PM IST for the trading day)
- No real-time intraday NAV estimates
- Cannot tell you which stocks a mutual fund holds (you need SEBI monthly portfolio disclosures for that)
- Single point of failure — if the service goes down, there's no exact equivalent (though you could build your own from AMFI's raw txt files)

### Recommendation for MCP server
Use as your **primary and sole source for mutual fund NAV data**. It's reliable, authoritative, and free. For mutual fund holdings/overlap analysis, you'll need to supplement with SEBI portfolio disclosure data (available quarterly with 45-day lag from AMC websites). Cache NAVs for 12-24 hours since they only update once daily.

---

## Source 4: Alpha Vantage (India tickers via `.BSE`)

**What it provides:** Stock prices, 50+ technical indicators (SMA, RSI, MACD, Bollinger Bands), fundamentals, news + sentiment analysis, economic indicators.

**The truth: Excellent data quality but the free tier is severely limited.** The free tier is limited to 25 requests per day. That's not 25 stocks — that's 25 total API calls across all endpoints.

### Rate limits
- **Free tier: 25 API requests per day** — this is the hard ceiling
- 25 requests per day disappears quickly if you're analyzing a diversified portfolio. Fetching a single stock's daily price history counts as one request. Getting technical indicators for that same stock is another request. Checking fundamental data is yet another
- Premium plans start at **$49.99/month** and go up to $249.99/month for higher throughput
- Premium removes daily limits and switches to per-minute rate limits

### Legal status
- Fully legitimate, licensed data provider
- **NASDAQ-licensed** data vendor — the data is properly sourced
- India coverage via `.BSE` ticker suffix (e.g., `RELIANCE.BSE`)
- Alpha Vantage now has an official MCP server for AI/LLM integration — directly relevant to your use case
- Commercial use allowed under their terms

### Advantages
- **Highest data quality** among free options — properly licensed, NASDAQ-backed
- 50+ pre-computed technical indicators (saves you from calculating RSI, MACD, etc. yourself)
- 20+ years of historical data for many tickers
- Fundamentals: income statements, balance sheets, cash flow, earnings
- News sentiment API with AI-powered scoring
- Official MCP server already exists — you could potentially wrap/extend it
- Clean, well-documented REST API with JSON/CSV output

### Limitations
- **25 requests/day is brutal** — supports roughly 8-12 complete stock analyses per day on free tier
- India coverage is via BSE only (`.BSE` suffix), not NSE
- Some fundamental data for Indian companies may be less complete than US stocks
- No real-time data on free tier — 15-minute delay
- No option chain data for Indian stocks on free tier

### Recommendation for MCP server
Use for **technical indicators and fundamentals as a premium/high-quality source**. Implement aggressive caching (24h for fundamentals, 6h for technicals, 30min for news sentiment). Use a request priority queue: user-initiated queries get Priority 1 (use Alpha Vantage), background refresh gets Priority 4 (use free alternatives). Consider the $49.99/month plan for production — it unlocks significantly more capacity and is cheap relative to the data quality.

---

## Source 5: Finnhub

**What it provides:** Company news, earnings calendar, recommendations, insider transactions, ESG data, economic calendars.

**The truth: Generous free tier, but India coverage is the weakest link.** Finnhub covers 60+ global exchanges. International coverage requires a paid plan. Quote quality varies by exchange — US data is real-time, while some international exchanges have 15-minute delays.

### Rate limits
- **Free tier: 60 API calls per minute** — by far the most generous among all APIs listed
- The free plan typically provides sufficient request capacity to support meaningful experimentation and early-stage prototypes
- WebSocket streaming available on free tier (limited to 50 symbols)
- Paid plans range from $11.99 to $99.99/month

### Legal status
- Fully legitimate, commercial data provider
- Built by ex-engineers from Google, Bloomberg, and Tradeweb (office in Mumbai)
- Free for development/non-commercial use; commercial use requires paid tier

### Advantages
- **60 requests/minute free** — 100x more generous than Alpha Vantage
- Company news feed with search and filtering — useful for sentiment analysis
- Earnings calendar with surprise data
- Insider transactions data
- Alternative data: congressional trading, lobbying data, supply chain relationships
- WebSocket for real-time trade data (limited symbols on free)
- Well-designed REST API with excellent documentation

### Limitations
- **India-specific coverage is partial** — basic price data for NSE stocks works, but deep fundamentals, analyst estimates, and earnings data are primarily US-focused
- Indian company news coverage is less comprehensive than what you'd get from NewsAPI or GNews
- Consensus estimates for Indian stocks are limited on free tier (this is a major gap for PS3 Earnings Command Center)
- Generous free-tier limits but limited free tier is primarily for evaluation. Request limits are restrictive on advanced features
- Historical data limited to 1 year per API call on free tier

### Recommendation for MCP server
Use primarily for **news, earnings calendar, and sentiment signals**. Don't rely on it for Indian stock prices or fundamentals (use broker APIs/yfinance instead). The 60 req/min free tier makes it excellent for polling company news. For PS3 (Earnings Command Center), Finnhub's earnings surprise data can supplement your own calculations, but don't expect complete Indian coverage.

---

## Source 6: BSE India (bseindia.com)

**What it provides:** Corporate announcements, board meetings, quarterly results, annual reports (PDFs), shareholding patterns, corporate actions, bulk/block deals.

**The truth: BSE has the richest corporate disclosure data in India, but no official free API.** Like NSE, access is through reverse-engineering web endpoints. Unlike NSE, BSE is slightly more permissive and its endpoints are more stable.

### Rate limits
- No documented rate limits, but aggressive scraping will get you IP-blocked
- The unofficial Python library `bse` (BseIndiaApi) is actively maintained and handles session management
- Endpoints for announcements, results, and corporate actions are relatively stable

### Legal status
- BSE provides corporate data through subscription products — Corporate Announcements, Results, Shareholding Pattern, Insider Trading
- Official data subscription for commercial use is available but costly (₹3 lakhs/year via vendors like Tickerplant)
- For a hackathon/MVP, scraping public BSE announcement pages is in a gray area — the data itself is mandated to be public by SEBI regulations
- In India only Tickerplant provides corporate announcement API, costing about 3 lakh per year

### Advantages
- **India's largest corporate filing repository** — 4,650+ listed companies
- Quarterly results in structured HTML and PDF formats
- Shareholding pattern data (promoter, FII, DII, retail %) — critical for PS1 and PS3
- Corporate action data (dividends, splits, bonuses, rights issues)
- Board meeting dates and results calendar
- The `BseIndiaApi` Python package is well-maintained with pagination support for announcements

### Limitations
- **No official API** — relies on reverse-engineering website endpoints
- Quarterly result PDFs have **inconsistent formats across companies** — no standardized structure
- PDF parsing is the hardest technical challenge (each company formats differently)
- Result PDFs may be scanned images rather than text-based PDFs for smaller companies
- Historical data goes back to 2006 but accessing it requires careful pagination
- No WebSocket or push notification — you must poll for new filings

### Recommendation for MCP server
Use as your **primary source for corporate filings, results, shareholding patterns, and announcements**. This is non-negotiable for all three use cases. Build a polling pipeline that checks for new announcements every 5-10 minutes during business hours. For PS3 (Earnings), implement LLM-based PDF extraction rather than building custom parsers — the format variability makes rule-based parsing impractical. Cache filings permanently (they don't change once published).

---

## Source 7: RBI DBIE (data.rbi.org.in)

**What it provides:** Macro data: repo rate, reverse repo rate, CRR, SLR, CPI inflation, WPI inflation, GDP growth, forex reserves, money supply, balance of payments, industrial production index.

**The truth: Authoritative government data, but no REST API.** DBIE is a data warehouse of the Department of Statistics and Information Management (DSIM), under the Reserve Bank of India, disseminating data across seven subject areas: Real Sector, Corporate Sector, Financial Sector, Financial Market, External Sector, Public Finance, and Socio-Economic Indicators.

### Rate limits
- No REST API exists — data is accessible via the web portal with download options (Excel, CSV, PDF)
- RBI launched the `RBIDATA` mobile app in February 2025 providing access to the same 11,000+ data series, but still no programmatic API
- The URL changed to `https://data.rbi.org.in` in June 2024 (the old `dbie.rbi.org.in` redirects)

### Legal status
- **Fully public government data** — free to use, research-friendly
- Users can use the data for their research work with courtesy to the Database on Indian Economy, Reserve Bank of India
- No restrictions on commercial use of the data itself (just attribute RBI)

### Advantages
- **Most authoritative source** for Indian macroeconomic data — it's the central bank's own data
- 11,000+ time series covering every major economic indicator
- Historical data going back decades for many series
- Updated regularly (monetary policy data updated same day, quarterly data within weeks)
- Covers SAARC Finance data as well
- Integrated with RBI's Centralised Information Management System (CIMS) since June 2023

### Limitations
- **No REST API** — the biggest problem. You must either:
  1. Scrape the web portal (fragile, portal changes structure periodically)
  2. Download CSV/Excel files manually or via automated scripts
  3. Build your own data ingestion pipeline from the downloadable datasets
- Data updates are not real-time — macro indicators are released on RBI's schedule (monthly/quarterly)
- The web portal's JavaScript-heavy interface makes scraping harder than simple HTML
- No webhook or notification system for when new data is published

### Recommendation for MCP server
Build a **scheduled data ingestion pipeline** that downloads key macro indicators weekly. Store them in your own database. Key series to pre-fetch: repo rate, CPI inflation (monthly), WPI inflation, forex reserves (weekly), GDP growth (quarterly), IIP (monthly), money supply aggregates. Cache these values for 7 days minimum (macro data changes infrequently). For the MCP server, expose pre-processed, cached macro data — don't try to query DBIE in real-time.

---

## Source 8: data.gov.in

**What it provides:** Government open data: economic indicators, sector-wise statistics, agriculture data, demographic data.

**The truth: Legitimate API exists, but data quality and relevance for financial intelligence are limited.**

### Rate limits
- data.gov.in provides an API with a free API key
- Python package `datagovindia` exists for easier access
- Rate limits are generous for the data volumes involved

### Legal status
- Official Indian government open data platform
- Free API key required (easy signup)
- Data is public domain — free for any use

### Advantages
- Official API with JSON/CSV responses — the only Indian government data source with a proper REST API
- Covers economic indicators that complement RBI DBIE
- Useful for sector-specific data (agriculture, industry, trade statistics)

### Limitations
- **Low relevance for real-time financial intelligence** — most data is annual or quarterly with significant lag
- Data quality is inconsistent — some datasets are incomplete or have formatting issues
- The financial data that matters most (stock prices, company financials) is not available here
- Limited overlap with what you'd actually need for the three MCP use cases
- Updates can be irregular

### Recommendation for MCP server
Use as a **supplementary source for macro context only** — e.g., GDP sector-wise breakdowns, trade statistics, agricultural output data. Low priority for implementation. The RBI DBIE data covers 90% of what you need for macro indicators. Only integrate data.gov.in if you need sector-specific economic data that DBIE doesn't cover.

---

## Source 9: NewsAPI.org / GNews

**What it provides:** Indian financial news articles with search and filtering, headlines, sources, publication dates.

**The truth: NewsAPI.org is restrictive for production; GNews is a better alternative for Indian financial news.**

### NewsAPI.org
- **100 requests/day on free tier** (reduced from previous limits)
- **Free tier is for development only** — production use requires a paid plan ($449/month for Business)
- Returns headlines, descriptions, source, URL, and published date
- India financial news coverage is decent but not comprehensive
- No sentiment analysis included — just raw articles

### GNews
- **100 requests/day on free tier**
- Better for Indian news — has good regional source coverage
- Supports language filtering (Hindi, English, etc.)
- Free tier allows commercial use (unlike NewsAPI.org)
- Returns similar data: title, description, content snippet, source, URL

### Alternatives worth considering
- **NewsData.io** — 200 credits/day free, India-specific news category, sentiment analysis included, commercial use allowed on free tier
- **Marketaux** — Finance-specific news API with sentiment scoring and entity recognition, 100 requests/day free
- **Google News RSS feeds** — Free, no rate limits, but requires parsing XML and no filtering by company

### Recommendation for MCP server
Use **GNews or NewsData.io as primary** (better India coverage, commercial-use-friendly free tier). Supplement with Finnhub's company news endpoint for stock-specific news. Implement your own sentiment analysis using FinBERT or the LLM layer rather than paying for a news API's built-in sentiment. Cache news articles for 30 minutes during market hours, 2 hours after market close.

---

## Source 10: Broker APIs (Angel One SmartAPI / Zerodha Kite Connect / ICICI Breeze)

**Not listed in the hackathon brief but arguably the most important data source for production.**

### Angel One SmartAPI
- Angel One API is available for free of cost to all — retail investors, startups, and fintech firms
- **Free**: Real-time quotes, historical OHLCV (NSE equity, 1min to daily candles), WebSocket streaming, portfolio data
- Rate limits: 10 orders/second, reasonable data query limits
- SDKs in Python, Java, NodeJS, Go, R
- **Critical change (April 2026)**: Static IP is now mandatory for API-based trading, and order rate limits of 10 OPS per exchange/segment are enforced
- Requires an Angel One demat account (free to open)
- MCP servers already exist (community-built)

### Zerodha Kite Connect
- **Free personal API access** for Zerodha account holders (announced 2024)
- ₹500/month for full developer API access (was ₹2,000 previously)
- Kite MCP already launched officially by Zerodha for Claude/Cursor integration
- Best documentation in the Indian broker API space
- Historical data, live quotes, portfolio, positions, margins

### ICICI Breeze API
- No charges at all to connect systems, create apps, or access historical data. Breeze gives 3 years of second-level LTP data
- Free real-time streaming OHLC data
- F&O historical data included
- SSL + multi-layer encryption
- Requires ICICI Direct trading account

### Why broker APIs are critical
- **Legally licensed** — broker APIs serve data under exchange licenses, so redistribution concerns are much lower when the user authenticates with their own broker account
- **Most reliable** — these are production trading systems with 99.9%+ uptime SLAs
- **Real-time** — genuine tick-by-tick data via WebSocket
- **Free** — Angel One and ICICI charge nothing; Zerodha charges ₹500/month for dev access

### Recommendation for MCP server
Use Angel One SmartAPI as your **primary data source** for market data. It's free, reliable, well-documented, and has real-time WebSocket streaming. For the MCP server architecture, have users authenticate via their own broker account (OAuth) — this solves both the data licensing problem and provides portfolio access. Zerodha Kite MCP already validates this architecture pattern.

---

## Data Source Priority Matrix

| Priority | Source | Use For | Reliability | Legal Risk | Cost |
|---|---|---|---|---|---|
| **P0** | Angel One SmartAPI | Real-time prices, historical OHLCV, portfolio | High | None (licensed) | Free |
| **P0** | MFapi.in | Mutual fund NAVs, scheme search | High | None | Free |
| **P0** | BSE India (scraped) | Corporate filings, results, shareholding | Medium | Low-Medium | Free |
| **P1** | Alpha Vantage | Technical indicators, fundamentals, news sentiment | High | None (licensed) | Free (25/day) |
| **P1** | Finnhub | Company news, earnings calendar, sentiment | High | None (licensed) | Free (60/min) |
| **P1** | GNews / NewsData.io | Indian financial news | Medium-High | None | Free (100-200/day) |
| **P2** | RBI DBIE | Macro indicators (repo rate, CPI, GDP) | High | None (govt data) | Free |
| **P2** | yfinance | Fallback for historical prices, financial statements | Low-Medium | Medium | Free |
| **P3** | data.gov.in | Supplementary economic data | Medium | None | Free |
| **P3** | NSE India (scraped) | Enrichment: option chains, FII/DII, delivery volumes | Medium | High | Free |

---

## Recommended Caching TTLs

| Data Type | Cache Duration | Rationale |
|---|---|---|
| Real-time stock price | 15-30 seconds (market hours) | Balance between freshness and API load |
| Intraday OHLCV | 60 seconds | Candle data changes every interval |
| End-of-day prices | Until next market open | Doesn't change after 3:30 PM IST |
| Company fundamentals | 6-24 hours | Changes quarterly at most |
| Quarterly results | 7+ days (permanent after parsing) | Published once, never changes |
| Mutual fund NAV | 12-24 hours | Updates once daily by ~11 PM IST |
| News articles | 5-15 minutes | New articles publish frequently |
| News sentiment scores | 30-60 minutes | Aggregate sentiment shifts slowly |
| Technical indicators | 6 hours | Recalculated from price data |
| Macro data (RBI rates) | 7 days | Changes only at RBI policy meetings (~6x/year) |
| Macro data (CPI/WPI) | 30 days | Monthly publication cycle |
| Corporate filings | Permanent | Filings don't change once published |
| Shareholding patterns | 7 days | Updated quarterly |

---

## The Bottom Line

For a hackathon MVP, you can get by with **4 sources**: Angel One SmartAPI (prices + portfolio), MFapi.in (mutual funds), BSE India scraping (filings), and Finnhub (news + earnings calendar). That covers at least 4 distinct data sources and 3 data types as required.

For a production startup, invest in: Alpha Vantage premium ($50/month), proper BSE corporate data pipeline, and your own macro data ingestion from RBI DBIE. The total API cost for a production-grade system is under **₹10,000/month** — remarkably cheap for the depth of data you get. The expensive part isn't the APIs — it's the engineering to normalize, cache, cross-reference, and handle failures gracefully across all these sources.
