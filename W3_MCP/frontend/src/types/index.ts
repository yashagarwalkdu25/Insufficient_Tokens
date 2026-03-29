export type Tier = "free" | "premium" | "analyst" | "admin";

export interface UserSession {
  id: string;
  name: string;
  email: string;
  tier: Tier;
  roles: string[];
  scopes: string[];
  accessToken: string;
}

export interface StockQuote {
  symbol: string;
  company_name: string;
  exchange: string;
  ltp: number;
  change: number;
  change_percent: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  timestamp: string;
  source: string;
  cache_status: "hit" | "miss" | "stale";
}

export interface PriceHistory {
  symbol: string;
  interval: string;
  candles: Candle[];
  source: string;
  cache_status: string;
}

export interface Candle {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface NewsItem {
  title: string;
  description: string;
  url: string;
  source: string;
  published_at: string;
  sentiment?: "positive" | "negative" | "neutral";
  sentiment_score?: number;
  image_url?: string;
}

export interface NewsSentiment {
  symbol: string;
  overall_sentiment: "bullish" | "bearish" | "neutral";
  sentiment_score: number;
  articles_analyzed: number;
  positive_count: number;
  negative_count: number;
  neutral_count: number;
  key_themes: string[];
  source: string;
}

export interface FinancialStatement {
  symbol: string;
  period: string;
  revenue: number;
  net_income: number;
  ebitda: number;
  eps: number;
  total_assets: number;
  total_liabilities: number;
  equity: number;
  source: string;
}

export interface KeyRatio {
  symbol: string;
  pe_ratio: number;
  pb_ratio: number;
  debt_to_equity: number;
  roe: number;
  roce: number;
  current_ratio: number;
  dividend_yield: number;
  market_cap: number;
  source: string;
}

export interface TechnicalIndicator {
  symbol: string;
  indicator: string;
  value: number;
  signal: "buy" | "sell" | "neutral";
  timestamp: string;
  source: string;
}

export interface MutualFund {
  scheme_code: string;
  scheme_name: string;
  nav: number;
  date: string;
  category: string;
  fund_house: string;
  source: string;
}

export interface Signal {
  source: string;
  signal_type: "price" | "fundamental" | "sentiment" | "macro";
  direction: number;
  confidence: number;
  evidence: string;
  timestamp: string;
}

export interface CrossSourceAnalysis {
  symbol: string;
  signals: Signal[];
  contradictions: string[];
  synthesis: string;
  overall_confidence: number;
  citations: Citation[];
  disclaimer: string;
}

export interface Citation {
  source: string;
  data_point: string;
  url?: string;
}

export interface ResearchBrief {
  symbol: string;
  company_name: string;
  summary: string;
  key_findings: string[];
  risk_factors: string[];
  outlook: "bullish" | "bearish" | "neutral";
  confidence: number;
  sources_used: string[];
  generated_at: string;
  disclaimer: string;
}

export interface MacroSnapshot {
  repo_rate: number;
  reverse_repo_rate: number;
  crr: number;
  slr: number;
  cpi_inflation: number;
  wpi_inflation: number;
  gdp_growth: number;
  forex_reserves: number;
  usd_inr: number;
  source: string;
  as_of: string;
}

export interface TierUpgradeRequest {
  id: number;
  user_id: number;
  username: string;
  email: string;
  current_tier: Tier;
  requested_tier: Tier;
  status: "pending" | "approved" | "rejected";
  requested_at: string;
  reviewed_at?: string;
  reviewed_by?: string;
  notes?: string;
}

export interface ApiStatus {
  name: string;
  status: "available" | "configured" | "not_configured" | "degraded" | "down";
  latency_ms?: number;
  quota_used?: number;
  quota_limit?: number;
}

export interface RateLimitInfo {
  tier: Tier;
  used: number;
  limit: number;
  reset_at: string;
}

export interface MCPToolResult<T = unknown> {
  data: T;
  source: string;
  cache_status: "hit" | "miss" | "stale";
  disclaimer?: string;
  latency_ms: number;
}
