"use client";

import { useState } from "react";
import { useSession, signIn } from "next-auth/react";
import {
  Sun, Loader2, AlertTriangle, TrendingUp, TrendingDown,
  BarChart3, Globe, Calendar, Bell, RefreshCw,
} from "lucide-react";
import { callMCPTool } from "@/lib/mcp-client";
import { MCP_CLIENT, TIER } from "@/lib/constants";
import { cn, formatCurrency, formatPercent, tierBadge, TIER_LEVELS, type Tier } from "@/lib/utils";

interface PortfolioSnapshot {
  total_invested: number;
  current_value: number;
  total_pnl: number;
  total_pnl_pct: number;
  holdings_count: number;
}

interface TopMover {
  symbol: string;
  change_pct: number;
  ltp: number;
}

interface SentimentFlag {
  symbol: string;
  sentiment: number;
  direction: string;
}

interface MacroSnapshot {
  repo_rate?: number;
  cpi_latest?: number;
  usd_inr?: number;
  nifty50_change_pct?: number;
}

interface EarningsEntry {
  symbol: string;
  date: string;
}

interface MorningBrief {
  greeting: string;
  generated_at: string;
  portfolio: PortfolioSnapshot;
  top_movers: TopMover[];
  sentiment_flags: SentimentFlag[];
  macro: MacroSnapshot;
  upcoming_earnings: EarningsEntry[];
  active_alerts: number;
  triggered_alerts: number;
  summary: string;
}

export default function MorningBriefPage() {
  const { data: session, status } = useSession();
  const tier = (session?.tier as string) ?? TIER.Free;
  const tierLevel = TIER_LEVELS[tier as Tier] ?? 0;
  const token = session?.accessToken;

  const [brief, setBrief] = useState<MorningBrief | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

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
          Sign in to generate your personalised morning brief.
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

  async function handleGenerate() {
    setLoading(true);
    setError("");
    try {
      const result = await callMCPTool("generate_morning_brief", {}, token);
      const raw = result as unknown as Record<string, unknown>;
      if (raw.error) {
        setError(raw.error as string);
        return;
      }
      setBrief(result.data as unknown as MorningBrief);
    } catch (e: unknown) {
      const msg = (e as Error).message;
      if (msg === MCP_CLIENT.Error.Forbidden) setError("Morning brief requires at least Free tier.");
      else setError("Failed to generate morning brief.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Sun className="h-6 w-6 text-amber-400" /> Morning Brief
          </h1>
          <p className="text-muted-foreground text-sm">
            Your personalised daily market summary
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className={cn("px-2 py-0.5 rounded-full text-xs font-medium border uppercase", tierBadge(tier))}>{tier}</span>
          <button
            onClick={handleGenerate}
            disabled={loading}
            className="px-4 py-2 rounded-lg bg-amber-600 text-white text-sm font-medium hover:bg-amber-500 disabled:opacity-50 flex items-center gap-2"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            {brief ? "Refresh" : "Generate Brief"}
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 shrink-0" /> {error}
        </div>
      )}

      {!brief && !loading && (
        <div className="text-center py-20 text-muted-foreground">
          <Sun className="h-16 w-16 mx-auto mb-4 opacity-20" />
          <p className="text-lg font-medium">Good morning!</p>
          <p className="text-sm mt-1">Click &quot;Generate Brief&quot; to get your personalised market summary.</p>
          <p className="text-xs mt-3 text-muted-foreground/60">
            Includes portfolio P&amp;L, top movers, sentiment flags, macro context, earnings calendar, and active alerts.
          </p>
        </div>
      )}

      {loading && !brief && (
        <div className="text-center py-16">
          <Loader2 className="h-10 w-10 animate-spin text-amber-400 mx-auto mb-4" />
          <p className="text-muted-foreground">Generating your brief&hellip;</p>
          <p className="text-xs text-muted-foreground/60 mt-1">Fetching portfolio, market data, sentiment, and macro indicators in parallel.</p>
        </div>
      )}

      {brief && (
        <div className="space-y-4">
          {/* Greeting */}
          <div className="rounded-xl border border-amber-500/30 bg-gradient-to-r from-amber-500/10 to-orange-500/5 p-5">
            <p className="text-lg font-semibold text-amber-200">{brief.greeting}</p>
            <p className="text-xs text-muted-foreground mt-1">Generated {new Date(brief.generated_at).toLocaleString("en-IN")}</p>
          </div>

          {/* Summary */}
          {brief.summary && (
            <div className="rounded-xl border border-border bg-card p-4">
              <p className="text-sm leading-relaxed whitespace-pre-wrap">{brief.summary}</p>
            </div>
          )}

          {/* Grid: Portfolio + Macro */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Portfolio Snapshot */}
            <div className="rounded-xl border border-border bg-card p-4 space-y-3">
              <h3 className="text-sm font-semibold flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-blue-400" /> Portfolio Snapshot
              </h3>
              {brief.portfolio ? (
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <span className="text-muted-foreground text-xs">Invested</span>
                    <p className="font-mono font-medium">{formatCurrency(brief.portfolio.total_invested)}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground text-xs">Current Value</span>
                    <p className="font-mono font-medium">{formatCurrency(brief.portfolio.current_value)}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground text-xs">Total P&L</span>
                    <p className={cn("font-mono font-medium", (brief.portfolio.total_pnl || 0) >= 0 ? "text-emerald-400" : "text-red-400")}>
                      {formatCurrency(brief.portfolio.total_pnl)} ({formatPercent(brief.portfolio.total_pnl_pct)})
                    </p>
                  </div>
                  <div>
                    <span className="text-muted-foreground text-xs">Holdings</span>
                    <p className="font-mono font-medium">{brief.portfolio.holdings_count}</p>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No holdings yet. Add stocks to your portfolio.</p>
              )}
            </div>

            {/* Macro Snapshot */}
            <div className="rounded-xl border border-border bg-card p-4 space-y-3">
              <h3 className="text-sm font-semibold flex items-center gap-2">
                <Globe className="h-4 w-4 text-emerald-400" /> Macro Context
              </h3>
              {brief.macro ? (
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <span className="text-muted-foreground text-xs">Nifty 50</span>
                    <p className={cn("font-mono font-medium", (brief.macro.nifty50_change_pct || 0) >= 0 ? "text-emerald-400" : "text-red-400")}>
                      {formatPercent(brief.macro.nifty50_change_pct)}
                    </p>
                  </div>
                  <div>
                    <span className="text-muted-foreground text-xs">USD/INR</span>
                    <p className="font-mono font-medium">{brief.macro.usd_inr ?? "—"}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground text-xs">Repo Rate</span>
                    <p className="font-mono font-medium">{brief.macro.repo_rate ? `${brief.macro.repo_rate}%` : "—"}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground text-xs">CPI</span>
                    <p className="font-mono font-medium">{brief.macro.cpi_latest ? `${brief.macro.cpi_latest}%` : "—"}</p>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">Macro data unavailable.</p>
              )}
            </div>
          </div>

          {/* Top Movers */}
          {brief.top_movers && brief.top_movers.length > 0 && (
            <div className="rounded-xl border border-border bg-card p-4 space-y-3">
              <h3 className="text-sm font-semibold flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-emerald-400" /> Top Movers in Your Portfolio
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {brief.top_movers.map((m) => (
                  <div key={m.symbol} className="rounded-lg bg-secondary/50 p-3 text-sm">
                    <p className="font-mono font-medium">{m.symbol}</p>
                    <p className={cn("text-xs font-medium", m.change_pct >= 0 ? "text-emerald-400" : "text-red-400")}>
                      {m.change_pct >= 0 ? <TrendingUp className="inline h-3 w-3 mr-0.5" /> : <TrendingDown className="inline h-3 w-3 mr-0.5" />}
                      {formatPercent(m.change_pct)}
                    </p>
                    <p className="text-xs text-muted-foreground">{formatCurrency(m.ltp)}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Sentiment Flags */}
          {brief.sentiment_flags && brief.sentiment_flags.length > 0 && (
            <div className="rounded-xl border border-amber-500/30 bg-card p-4 space-y-3">
              <h3 className="text-sm font-semibold flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-400" /> Sentiment Flags
              </h3>
              <div className="space-y-2">
                {brief.sentiment_flags.map((f) => (
                  <div key={f.symbol} className="flex items-center justify-between text-sm rounded-lg bg-secondary/50 p-3">
                    <span className="font-mono font-medium">{f.symbol}</span>
                    <span className={cn("text-xs font-medium", f.direction === "positive" ? "text-emerald-400" : "text-red-400")}>
                      {f.direction} (score: {typeof f.sentiment === "number" ? f.sentiment.toFixed(2) : f.sentiment})
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Grid: Earnings + Alerts */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Upcoming Earnings */}
            {brief.upcoming_earnings && brief.upcoming_earnings.length > 0 && (
              <div className="rounded-xl border border-purple-500/30 bg-card p-4 space-y-3">
                <h3 className="text-sm font-semibold flex items-center gap-2">
                  <Calendar className="h-4 w-4 text-purple-400" /> Upcoming Earnings
                </h3>
                <div className="space-y-1">
                  {brief.upcoming_earnings.slice(0, 6).map((e, i) => (
                    <div key={i} className="flex items-center justify-between text-sm py-1 border-b border-border/50 last:border-0">
                      <span className="font-mono">{e.symbol}</span>
                      <span className="text-xs text-muted-foreground">{e.date}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Alert Status */}
            <div className="rounded-xl border border-border bg-card p-4 space-y-3">
              <h3 className="text-sm font-semibold flex items-center gap-2">
                <Bell className="h-4 w-4 text-blue-400" /> Alert Status
              </h3>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="rounded-lg bg-secondary/50 p-3 text-center">
                  <p className="text-2xl font-bold text-blue-400">{brief.active_alerts ?? 0}</p>
                  <p className="text-xs text-muted-foreground">Active</p>
                </div>
                <div className="rounded-lg bg-secondary/50 p-3 text-center">
                  <p className={cn("text-2xl font-bold", (brief.triggered_alerts ?? 0) > 0 ? "text-red-400" : "text-muted-foreground")}>{brief.triggered_alerts ?? 0}</p>
                  <p className="text-xs text-muted-foreground">Triggered</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
