"use client";

import { useState } from "react";
import { useSession, signIn } from "next-auth/react";
import { Search, TrendingUp, TrendingDown, AlertTriangle, FileText, Loader2, Lock, BarChart3, Zap, Crown } from "lucide-react";
import { callMCPTool } from "@/lib/mcp-client";
import { MCP_CLIENT, TIER } from "@/lib/constants";
import { cn, formatCurrency, formatPercent, tierBadge, TIER_LEVELS, type Tier } from "@/lib/utils";
import { TrustScorePanel } from "@/components/trust-score-panel";

interface QuoteData {
  symbol: string;
  ltp: number | null;
  change_pct: number | null;
  volume: number | null;
  market_cap: number | null;
  week_52_high: number | null;
  week_52_low: number | null;
  open: number | null;
  high: number | null;
  low: number | null;
}

interface NewsArticle {
  title: string;
  source: string;
  url: string;
  published_at: string;
}

interface SignalData {
  source: string;
  signal_type: string;
  direction: number;
  confidence: number;
  evidence: string;
}

interface FundamentalsData {
  pe_ratio: number | null;
  pb_ratio: number | null;
  roe: number | null;
  debt_to_equity: number | null;
  eps: number | null;
  dividend_yield: number | null;
  revenue_growth: number | null;
  _source?: string;
}

interface ShareholdingData {
  promoter: number | null;
  fii: number | null;
  dii: number | null;
  retail: number | null;
  _source?: string;
}

// Extract a valid ticker symbol from natural language input
// e.g. "what about TCS" → "TCS", "RELIANCE" → "RELIANCE"
function extractSymbol(input: string): string | null {
  const cleaned = input.trim().toUpperCase();
  // If the whole input looks like a ticker, use it directly
  if (/^[A-Z0-9&_.-]{1,20}$/.test(cleaned)) return cleaned;
  // Otherwise, scan words for a valid ticker pattern (2+ chars, starts with letter)
  const words = cleaned.split(/\s+/);
  for (const w of words.reverse()) {
    if (/^[A-Z][A-Z0-9&_.-]{0,19}$/.test(w) && w.length >= 2) return w;
  }
  return null;
}

export default function ResearchPage() {
  const { data: session, status } = useSession();
  const tier = (session?.tier as string) ?? TIER.Free;
  const tierLevel = TIER_LEVELS[tier as Tier] ?? 0;

  const [symbol, setSymbol] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingPremium, setLoadingPremium] = useState(false);
  const [loadingAnalyst, setLoadingAnalyst] = useState(false);
  const [quote, setQuote] = useState<QuoteData | null>(null);
  const [news, setNews] = useState<NewsArticle[]>([]);
  const [fundamentals, setFundamentals] = useState<FundamentalsData | null>(null);
  const [shareholding, setShareholding] = useState<ShareholdingData | null>(null);
  const [signals, setSignals] = useState<SignalData[]>([]);
  const [contradictions, setContradictions] = useState<string[]>([]);
  const [synthesis, setSynthesis] = useState("");
  const [analysisSource, setAnalysisSource] = useState("");
  const [citations, setCitations] = useState<{source: string; data_point: string; value?: string}[]>([]);
  const [trustMeta, setTrustMeta] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const [source, setSource] = useState("");

  // --- AUTH GATE: require login (after all hooks) ---
  if (status === "loading") {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (status === "unauthenticated" || !session) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-4">
        <AlertTriangle className="h-12 w-12 text-amber-400" />
        <h2 className="text-xl font-bold">Authentication Required</h2>
        <p className="text-muted-foreground text-center max-w-md">
          You must sign in to access the Research Copilot. Your tier determines which tools are available.
        </p>
        <button
          onClick={() => signIn()}
          className="px-6 py-3 rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90 transition-colors"
        >
          Sign In to Continue
        </button>
      </div>
    );
  }

  function resetAll() {
    setQuote(null);
    setNews([]);
    setFundamentals(null);
    setShareholding(null);
    setSignals([]);
    setContradictions([]);
    setSynthesis("");
    setCitations([]);
    setAnalysisSource("");
    setTrustMeta(null);
    setSource("");
  }

  // ─── FREE: Quote + News ─────────────────────────────────────────
  async function handleSearch() {
    if (!symbol.trim()) return;
    const ticker = extractSymbol(symbol);
    if (!ticker) {
      setError(`Could not find a valid ticker in "${symbol}". Try entering just the symbol (e.g. TCS, RELIANCE, INFY).`);
      return;
    }
    setLoading(true);
    setError("");
    resetAll();

    try {
      const token = session?.accessToken;
      const quoteResult = await callMCPTool("get_stock_quote", { symbol: ticker }, token);
      const raw = quoteResult as unknown as Record<string, unknown>;
      if (raw.error) {
        setError(raw.error as string);
        return;
      }
      setQuote(quoteResult.data as unknown as QuoteData);
      setSource(quoteResult.source);

      const newsResult = await callMCPTool("get_company_news", { symbol: ticker, days: 7 }, token);
      setNews(((newsResult.data as Record<string, unknown>)?.articles as NewsArticle[]) || []);
    } catch (e: unknown) {
      const msg = (e as Error).message;
      if (msg === MCP_CLIENT.Error.Forbidden) setError("Upgrade your tier to access this tool.");
      else if (msg === MCP_CLIENT.Error.Unauthorized) setError("Please sign in again — your session may have expired.");
      else setError("Failed to fetch data. Check MCP server connection.");
    } finally {
      setLoading(false);
    }
  }

  // ─── PREMIUM: Quick Analysis (fundamentals + shareholding) ──────
  async function handleQuickAnalysis() {
    const ticker = extractSymbol(symbol);
    if (!ticker) return;
    setLoadingPremium(true);
    setError("");

    try {
      const token = session?.accessToken;
      const [fundResult, shareResult] = await Promise.all([
        callMCPTool("get_key_ratios", { symbol: ticker }, token),
        callMCPTool("get_shareholding_pattern", { symbol: ticker }, token),
      ]);
      const fundRaw = fundResult as unknown as Record<string, unknown>;
      if (!fundRaw.error) {
        setFundamentals(fundResult.data as unknown as FundamentalsData);
      }
      const shareRaw = shareResult as unknown as Record<string, unknown>;
      if (!shareRaw.error) {
        const shareData = shareResult.data as Record<string, unknown>;
        const entries = (shareData?.entries as Record<string, unknown>[]) || [];
        if (entries.length > 0) {
          setShareholding(entries[0] as unknown as ShareholdingData);
        }
      }
    } catch (e: unknown) {
      const msg = (e as Error).message;
      if (msg === MCP_CLIENT.Error.Forbidden) setError("Quick Analysis requires Premium tier or higher.");
      else if (msg === MCP_CLIENT.Error.Unauthorized) setError("Please sign in again — your session may have expired.");
      else setError("Failed to fetch fundamentals. " + msg);
    } finally {
      setLoadingPremium(false);
    }
  }

  // ─── ANALYST: Deep Dive (cross-source signals + research brief) ─
  async function handleDeepDive() {
    const ticker = extractSymbol(symbol);
    if (!ticker) return;
    setLoadingAnalyst(true);
    setError("");
    try {
      const token = session?.accessToken;
      const result = await callMCPTool("cross_reference_signals", { symbol: ticker }, token);
      const raw = result as unknown as Record<string, unknown>;
      if (raw.error) {
        setError(raw.error as string);
        return;
      }
      const data = (result.data ?? result) as Record<string, unknown>;
      if (data.error) {
        setError(data.error as string);
        return;
      }
      setSignals((data.signals as SignalData[]) || []);
      setContradictions((data.contradictions as string[]) || []);
      setSynthesis((data.synthesis as string) || "");
      setCitations((data.citations as {source: string; data_point: string; value?: string}[]) || []);
      setAnalysisSource(result.source || "");
      setTrustMeta({
        trust_score: data.trust_score,
        signal_summary: data.signal_summary,
        conflicts: data.conflicts,
        trust_score_reasoning: data.trust_score_reasoning,
      });
    } catch (e: unknown) {
      const msg = (e as Error).message;
      if (msg === MCP_CLIENT.Error.Forbidden) setError("Deep Dive requires Analyst tier.");
      else if (msg === MCP_CLIENT.Error.Unauthorized) setError("Please sign in again — your session may have expired.");
      else setError("Failed to run deep dive analysis.");
    } finally {
      setLoadingAnalyst(false);
    }
  }

  const anyLoading = loading || loadingPremium || loadingAnalyst;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Research Copilot</h1>
          <p className="text-muted-foreground">Full-stack research assistant for Indian equities</p>
        </div>
        <span className={cn("px-3 py-1 rounded-full text-xs font-bold border uppercase tracking-wider", tierBadge(tier))}>
          {tier}
        </span>
      </div>

      {/* Search Bar */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Enter stock symbol (e.g. RELIANCE, TCS, INFY)"
            value={symbol}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSymbol(e.target.value.toUpperCase())}
            onKeyDown={(e: React.KeyboardEvent) => e.key === "Enter" && handleSearch()}
            className="w-full pl-10 pr-4 py-2.5 rounded-lg bg-card border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
          />
        </div>
        <button onClick={handleSearch} disabled={anyLoading} className="px-4 py-2.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50">
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Analyze"}
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 shrink-0" /> {error}
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════
          SECTION 1 — FREE: Quote + News (All tiers)
          ═══════════════════════════════════════════════════════════════ */}
      {quote && (
        <div className="rounded-xl border border-border bg-card p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-xl font-bold">{quote.symbol}</h2>
              <p className="text-xs text-muted-foreground">Source: {source}</p>
            </div>
            <div className="text-right">
              <p className="text-2xl font-bold">{formatCurrency(quote.ltp)}</p>
              <p className={cn("text-sm font-medium", (quote.change_pct || 0) >= 0 ? "text-emerald-400" : "text-red-400")}>
                {(quote.change_pct || 0) >= 0 ? <TrendingUp className="inline h-4 w-4 mr-1" /> : <TrendingDown className="inline h-4 w-4 mr-1" />}
                {formatPercent(quote.change_pct)}
              </p>
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div><span className="text-muted-foreground">Open</span><p className="font-medium">{formatCurrency(quote.open)}</p></div>
            <div><span className="text-muted-foreground">High</span><p className="font-medium">{formatCurrency(quote.high)}</p></div>
            <div><span className="text-muted-foreground">Low</span><p className="font-medium">{formatCurrency(quote.low)}</p></div>
            <div><span className="text-muted-foreground">Volume</span><p className="font-medium">{quote.volume?.toLocaleString("en-IN") || "—"}</p></div>
            <div><span className="text-muted-foreground">52W High</span><p className="font-medium">{formatCurrency(quote.week_52_high)}</p></div>
            <div><span className="text-muted-foreground">52W Low</span><p className="font-medium">{formatCurrency(quote.week_52_low)}</p></div>
            <div><span className="text-muted-foreground">Market Cap</span><p className="font-medium">{quote.market_cap ? `₹${(quote.market_cap / 1e7).toFixed(0)} Cr` : "—"}</p></div>
          </div>
        </div>
      )}

      {/* News (Free) */}
      {news.length > 0 && (
        <div className="rounded-xl border border-border bg-card p-6">
          <h3 className="font-semibold mb-3 flex items-center gap-2"><FileText className="h-4 w-4" /> Recent News</h3>
          <div className="space-y-3">
            {news.slice(0, 5).map((a: NewsArticle, i: number) => (
              <div key={i} className="text-sm border-b border-border pb-2 last:border-0">
                <a href={a.url} target="_blank" rel="noopener noreferrer" className="font-medium hover:text-primary transition-colors">{a.title}</a>
                <p className="text-muted-foreground text-xs">{a.source} · {a.published_at}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════
          SECTION 2 — PREMIUM: Quick Analysis (fundamentals + shareholding)
          ═══════════════════════════════════════════════════════════════ */}
      {quote && (
        <div className={cn("rounded-xl border bg-card p-6 space-y-4", tierLevel >= 1 ? "border-blue-500/30" : "border-border opacity-60")}>
          <div className="flex items-center justify-between">
            <h3 className="font-semibold flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-blue-400" /> Quick Analysis
            </h3>
            <div className="flex items-center gap-2">
              <span className={cn("px-2 py-0.5 rounded-full text-xs border", tierBadge(TIER.Premium))}>Premium+</span>
              {tierLevel >= 1 ? (
                <button onClick={handleQuickAnalysis} disabled={anyLoading} className="px-3 py-1.5 rounded-md bg-blue-600 text-white text-xs font-medium hover:bg-blue-500 disabled:opacity-50">
                  {loadingPremium ? <Loader2 className="h-3 w-3 animate-spin" /> : "Run Quick Analysis"}
                </button>
              ) : (
                <span className="flex items-center gap-1 text-xs text-muted-foreground"><Lock className="h-3 w-3" /> Upgrade to Premium</span>
              )}
            </div>
          </div>

          {tierLevel < 1 && (
            <p className="text-xs text-muted-foreground">Includes financial ratios (P/E, ROE, D/E), shareholding pattern, and sector comparison. Upgrade to Premium to unlock.</p>
          )}

          {/* Fundamentals */}
          {fundamentals && (
            <div className="space-y-2">
              <p className="text-xs font-medium text-blue-300">Key Financial Ratios</p>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                <div className="p-2 rounded-lg bg-secondary/50"><span className="text-muted-foreground text-xs">P/E Ratio</span><p className="font-mono font-medium">{fundamentals.pe_ratio?.toFixed(1) ?? "—"}</p></div>
                <div className="p-2 rounded-lg bg-secondary/50"><span className="text-muted-foreground text-xs">P/B Ratio</span><p className="font-mono font-medium">{fundamentals.pb_ratio?.toFixed(1) ?? "—"}</p></div>
                <div className="p-2 rounded-lg bg-secondary/50"><span className="text-muted-foreground text-xs">ROE</span><p className="font-mono font-medium">{fundamentals.roe ? `${(fundamentals.roe < 1 ? fundamentals.roe * 100 : fundamentals.roe).toFixed(1)}%` : "—"}</p></div>
                <div className="p-2 rounded-lg bg-secondary/50"><span className="text-muted-foreground text-xs">Debt/Equity</span><p className="font-mono font-medium">{fundamentals.debt_to_equity?.toFixed(2) ?? "—"}</p></div>
                <div className="p-2 rounded-lg bg-secondary/50"><span className="text-muted-foreground text-xs">EPS</span><p className="font-mono font-medium">{fundamentals.eps ? `₹${fundamentals.eps.toFixed(1)}` : "—"}</p></div>
                <div className="p-2 rounded-lg bg-secondary/50"><span className="text-muted-foreground text-xs">Div Yield</span><p className="font-mono font-medium">{fundamentals.dividend_yield ? `${(fundamentals.dividend_yield < 1 ? fundamentals.dividend_yield * 100 : fundamentals.dividend_yield).toFixed(2)}%` : "—"}</p></div>
              </div>
            </div>
          )}

          {/* Shareholding */}
          {shareholding && (
            <div className="space-y-2">
              <p className="text-xs font-medium text-blue-300">Shareholding Pattern</p>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                <div className="p-2 rounded-lg bg-secondary/50"><span className="text-muted-foreground text-xs">Promoter</span><p className="font-mono font-medium">{shareholding.promoter ? `${shareholding.promoter.toFixed(1)}%` : "—"}</p></div>
                <div className="p-2 rounded-lg bg-secondary/50"><span className="text-muted-foreground text-xs">FII</span><p className="font-mono font-medium">{shareholding.fii ? `${shareholding.fii.toFixed(1)}%` : "—"}</p></div>
                <div className="p-2 rounded-lg bg-secondary/50"><span className="text-muted-foreground text-xs">DII</span><p className="font-mono font-medium">{shareholding.dii ? `${shareholding.dii.toFixed(1)}%` : "—"}</p></div>
                <div className="p-2 rounded-lg bg-secondary/50"><span className="text-muted-foreground text-xs">Public/Retail</span><p className="font-mono font-medium">{shareholding.retail ? `${shareholding.retail.toFixed(1)}%` : "—"}</p></div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════
          SECTION 3 — ANALYST: Deep Dive (cross-source + research brief)
          ═══════════════════════════════════════════════════════════════ */}
      {quote && (
        <div className={cn("rounded-xl border bg-card p-6 space-y-4", tierLevel >= 2 ? "border-purple-500/30" : "border-border opacity-60")}>
          <div className="flex items-center justify-between">
            <h3 className="font-semibold flex items-center gap-2">
              <Zap className="h-4 w-4 text-purple-400" /> Deep Dive — Cross-Source Analysis
            </h3>
            <div className="flex items-center gap-2">
              <span className={cn("px-2 py-0.5 rounded-full text-xs border", tierBadge(TIER.Analyst))}>Analyst Only</span>
              {tierLevel >= 2 ? (
                <button onClick={handleDeepDive} disabled={anyLoading} className="px-3 py-1.5 rounded-md bg-purple-600 text-white text-xs font-medium hover:bg-purple-500 disabled:opacity-50">
                  {loadingAnalyst ? <Loader2 className="h-3 w-3 animate-spin" /> : "Run Deep Dive"}
                </button>
              ) : (
                <span className="flex items-center gap-1 text-xs text-muted-foreground"><Lock className="h-3 w-3" /> Upgrade to Analyst</span>
              )}
            </div>
          </div>

          {tierLevel < 2 && (
            <p className="text-xs text-muted-foreground">Pulls from 5+ sources (Angel One, Alpha Vantage, Finnhub, BSE, RBI DBIE), runs CrewAI multi-agent analysis, generates research brief with citations. Analyst tier only.</p>
          )}

          {analysisSource && (
            <p className="text-xs text-muted-foreground">Powered by: <span className="text-purple-400 font-medium">{analysisSource === "crewai_research_crew" ? "CrewAI Multi-Agent Research Crew (5 agents)" : analysisSource}</span></p>
          )}

          <TrustScorePanel payload={trustMeta} />

          {signals.length > 0 && (
            <div className="space-y-2">
              {signals.map((s: SignalData, i: number) => (
                <div key={i} className="p-3 rounded-lg bg-secondary/50 text-sm space-y-1">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="font-medium capitalize">{s.signal_type}</span>
                      <span className="text-muted-foreground ml-2">[{s.source}]</span>
                    </div>
                    <div className="flex items-center gap-4">
                      <span className={cn("font-mono", s.direction > 0 ? "text-emerald-400" : s.direction < 0 ? "text-red-400" : "text-muted-foreground")}>
                        {s.direction > 0 ? "▲" : s.direction < 0 ? "▼" : "—"} {s.direction.toFixed(2)}
                      </span>
                      <span className="text-muted-foreground text-xs">conf: {(s.confidence * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                  {s.evidence && <p className="text-xs text-muted-foreground/80">{s.evidence}</p>}
                </div>
              ))}
            </div>
          )}

          {synthesis && (
            <div className="rounded-lg border border-blue-500/30 bg-blue-500/10 p-4 space-y-2">
              <p className="text-sm font-medium text-blue-300">AI Synthesis</p>
              <p className="text-sm text-blue-100/90 leading-relaxed whitespace-pre-wrap">{synthesis}</p>
            </div>
          )}

          {citations.length > 0 && (
            <div className="rounded-lg border border-border/50 bg-secondary/30 p-3 space-y-1">
              <p className="text-xs font-medium text-muted-foreground">Source Citations ({citations.length})</p>
              {citations.map((c: {source: string; data_point: string; value?: string}, i: number) => (
                <p key={i} className="text-xs text-muted-foreground/70">• <span className="text-foreground/80 font-medium">{c.source}</span>: {c.data_point}{c.value ? ` = ${c.value}` : ""}</p>
              ))}
            </div>
          )}

          {contradictions.length > 0 && (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 space-y-1">
              <p className="text-sm font-medium text-amber-300 flex items-center gap-1"><AlertTriangle className="h-4 w-4" /> Cross-Source Contradictions</p>
              {contradictions.map((c: string, i: number) => (
                <p key={i} className="text-xs text-amber-200/80">• {c}</p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
