"use client";

import { useState } from "react";
import { useSession, signIn } from "next-auth/react";
import {
  BarChart3, Calendar, Target, AlertTriangle, Loader2,
  TrendingUp, Lock, FileText, Activity, Users, ArrowUpDown,
  Shield, Zap, Eye, ExternalLink, Star, Clock, HelpCircle,
} from "lucide-react";
import { callMCPTool } from "@/lib/mcp-client";
import {
  EARNINGS_PANEL_FETCH,
  earningsPanelIsPremium,
  type EarningsPanelKey,
} from "@/lib/earnings-panels";
import { MCP_CLIENT, TIER } from "@/lib/constants";
import { cn, tierBadge, TIER_LEVELS, type Tier } from "@/lib/utils";
import { TrustScorePanel } from "@/components/trust-score-panel";

export default function EarningsPage() {
  const { data: session, status } = useSession();
  const tier = session?.tier ?? TIER.Free;
  const tierLevel = TIER_LEVELS[tier as Tier] ?? 0;
  const token = session?.accessToken;

  const [calendar, setCalendar] = useState<Record<string, unknown>[]>([]);
  const [calendarFilter, setCalendarFilter] = useState<string>("india");
  const [calendarCount, setCalendarCount] = useState(0);
  const [symbol, setSymbol] = useState("");
  const [epsHistory, setEpsHistory] = useState<Record<string, unknown> | null>(null);
  const [preProfile, setPreProfile] = useState<Record<string, unknown> | null>(null);
  const [expectations, setExpectations] = useState<Record<string, unknown> | null>(null);
  const [postReaction, setPostReaction] = useState<Record<string, unknown> | null>(null);
  const [actualVsExpected, setActualVsExpected] = useState<Record<string, unknown> | null>(null);
  const [optionChain, setOptionChain] = useState<Record<string, unknown> | null>(null);
  const [verdict, setVerdict] = useState<Record<string, unknown> | null>(null);
  const [dashboard, setDashboard] = useState<Record<string, unknown> | null>(null);
  const [comparison, setComparison] = useState<Record<string, unknown> | null>(null);
  const [compareSymbols, setCompareSymbols] = useState("TCS,INFY,WIPRO");
  const [loading, setLoading] = useState("");
  const [error, setError] = useState("");

  /** Panel open = show block; click again to hide and clear data (checkbox-style). */
  const [openPanels, setOpenPanels] = useState<Partial<Record<EarningsPanelKey, boolean>>>({});

  function setLoad(key: string) { setLoading(key); setError(""); }
  function clearLoad() { setLoading(""); }

  function setPanelData(key: EarningsPanelKey, data: Record<string, unknown> | null) {
    switch (key) {
      case "eps":
        setEpsHistory(data);
        break;
      case "pre":
        setPreProfile(data);
        break;
      case "expect":
        setExpectations(data);
        break;
      case "options":
        setOptionChain(data);
        break;
      case "reaction":
        setPostReaction(data);
        break;
      case "avse":
        setActualVsExpected(data);
        break;
      case "verdict":
        setVerdict(data);
        break;
      case "dashboard":
        setDashboard(data);
        break;
      case "compare":
        setComparison(data);
        break;
    }
  }

  function closePanel(key: EarningsPanelKey) {
    setOpenPanels((o: Partial<Record<EarningsPanelKey, boolean>>) => ({ ...o, [key]: false }));
    setPanelData(key, null);
  }

  const panelBtn = (active: boolean, premium: boolean) =>
    cn(
      "px-3 py-1.5 rounded-md text-xs font-medium transition-colors border disabled:opacity-50",
      premium
        ? active
          ? "bg-amber-500 text-white border-amber-300 ring-2 ring-amber-400/60"
          : "bg-amber-600/80 text-white border-transparent hover:bg-amber-500"
        : active
          ? "bg-purple-500 text-white border-purple-300 ring-2 ring-purple-400/60"
          : "bg-purple-600 text-white border-transparent hover:bg-purple-500",
    );

  function panelButtonDisabled(key: EarningsPanelKey) {
    const spec = EARNINGS_PANEL_FETCH[key];
    if (openPanels[key]) return !!loading;
    if (spec.needsCompareSymbols) return !!loading || !compareSymbols.trim();
    if (spec.needsSymbol) return !!loading || !symbol.trim();
    return !!loading;
  }

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
          You must sign in to access the Earnings Command Center. Your tier determines which tools are available.
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

  async function loadCalendar(filterOverride?: string) {
    const f = filterOverride ?? calendarFilter;
    setLoad("calendar");
    try {
      const result = await callMCPTool("get_earnings_calendar", { weeks: 4, filter: f }, token);
      const data = result.data as Record<string, unknown>;
      setCalendar((data.entries as Record<string, unknown>[]) || []);
      setCalendarCount((data.total_count as number) || 0);
    } catch { setError("Failed to load earnings calendar."); }
    finally { clearLoad(); }
  }

  async function togglePanel(key: EarningsPanelKey) {
    const spec = EARNINGS_PANEL_FETCH[key];
    if (openPanels[key]) {
      closePanel(key);
      return;
    }
    if (spec.needsCompareSymbols && !compareSymbols.trim()) return;
    if (spec.needsSymbol && !symbol.trim()) return;
    setLoad(key);
    try {
      const ctx = {
        symbolUpper: symbol.trim().toUpperCase(),
        compareSymbols: compareSymbols.trim(),
      };
      const result = await callMCPTool(spec.tool, spec.buildBody(ctx), token);
      setPanelData(key, result.data as Record<string, unknown>);
      setOpenPanels((o: Partial<Record<EarningsPanelKey, boolean>>) => ({ ...o, [key]: true }));
    } catch (e) {
      const msg = (e as Error).message;
      setError(msg === MCP_CLIENT.Error.Forbidden ? spec.forbiddenMsg : spec.loadFailedMsg);
    } finally {
      clearLoad();
    }
  }

  const isLoading = (key: string) => loading === key;
  const Spin = () => <Loader2 className="h-3 w-3 animate-spin inline" />;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <BarChart3 className="h-6 w-6" /> Earnings Season Command Center
        </h1>
        <p className="text-muted-foreground">
          Earnings calendar, pre/post analysis, cross-source verdicts &mdash; your results season war room
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive flex items-center gap-2">
          <AlertTriangle className="h-4 w-4" /> {error}
        </div>
      )}

      {/* ================================================================= */}
      {/* SECTION 1: FREE — Earnings Calendar */}
      {/* ================================================================= */}
      <div className="rounded-xl border border-border bg-card p-5 space-y-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h3 className="font-semibold flex items-center gap-2">
            <Calendar className="h-4 w-4 text-emerald-400" /> Upcoming Earnings
            <span className={cn("px-2 py-0.5 rounded-full text-xs border", tierBadge(TIER.Free))}>Free</span>
            {calendarCount > 0 && <span className="text-xs text-muted-foreground">({calendarCount} results)</span>}
          </h3>
          <div className="flex items-center gap-2">
            <div className="flex rounded-md border border-border overflow-hidden text-xs">
              {(["india", "nifty50", "all"] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => { setCalendarFilter(f); if (calendar.length > 0) loadCalendar(f); }}
                  className={cn(
                    "px-2.5 py-1 capitalize transition-colors",
                    calendarFilter === f ? "bg-primary text-primary-foreground" : "hover:bg-secondary"
                  )}
                >
                  {f === "nifty50" ? "Nifty 50" : f === "all" ? "All" : "India"}
                </button>
              ))}
            </div>
            <button onClick={() => loadCalendar()} disabled={!!loading} className="px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-medium hover:bg-primary/90 disabled:opacity-50">
              {isLoading("calendar") ? <Spin /> : "Load Calendar"}
            </button>
          </div>
        </div>
        {calendar.length > 0 ? (
          <>
            {/* Group entries by week_group */}
            {(() => {
              const groups: Record<string, Record<string, unknown>[]> = {};
              const order: string[] = [];
              for (const e of calendar) {
                const g = (e.week_group as string) || "TBD";
                if (!groups[g]) { groups[g] = []; order.push(g); }
                groups[g].push(e);
              }
              return order.map((group) => (
                <div key={group} className="space-y-1.5">
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5 mt-2">
                    <Clock className="h-3 w-3" /> {group}
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                    {groups[group].map((e, i) => {
                      const inPortfolio = e.in_portfolio as boolean;
                      const isNifty = e.is_nifty50 as boolean;
                      const dateTbd = e.date_tbd as boolean;
                      const links = e.verify_links as Record<string, string> | null;
                      return (
                        <div
                          key={i}
                          className={cn(
                            "p-3 rounded-lg text-sm border",
                            inPortfolio ? "border-emerald-500/40 bg-emerald-500/10" : "border-transparent bg-secondary/50"
                          )}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="min-w-0 flex-1">
                              <p className="font-medium flex items-center gap-1.5 truncate">
                                {inPortfolio && <Star className="h-3 w-3 text-emerald-400 shrink-0" />}
                                {(e.symbol as string) || "—"}
                                {isNifty && <span className="text-[10px] px-1 py-0.5 rounded bg-blue-500/20 text-blue-300">N50</span>}
                              </p>
                              {(e.company_name as string) && (
                                <p className="text-xs text-muted-foreground truncate">{e.company_name as string} &mdash; {(e.exchange as string) || "NSE"}</p>
                              )}
                              {(e.sector as string) && (
                                <p className="text-[10px] text-muted-foreground/70">{e.sector as string}</p>
                              )}
                            </div>
                            {links && (
                              <div className="flex gap-1 shrink-0">
                                {(links.nse) && (
                                  <a href={links.nse} target="_blank" rel="noopener noreferrer" className="text-[10px] text-blue-400 hover:text-blue-300 flex items-center gap-0.5">
                                    NSE <ExternalLink className="h-2.5 w-2.5" />
                                  </a>
                                )}
                                {(links.bse) && (
                                  <a href={links.bse} target="_blank" rel="noopener noreferrer" className="text-[10px] text-blue-400 hover:text-blue-300 flex items-center gap-0.5">
                                    BSE <ExternalLink className="h-2.5 w-2.5" />
                                  </a>
                                )}
                              </div>
                            )}
                          </div>
                          <div className="flex items-center gap-2 mt-1.5 text-xs text-muted-foreground">
                            {dateTbd ? (
                              <span className="flex items-center gap-1 text-amber-400" title={e.tbd_reason as string}>
                                <HelpCircle className="h-3 w-3" /> TBD
                              </span>
                            ) : (
                              <span>{e.expected_date as string}</span>
                            )}
                            {e.days_away != null && !dateTbd && (
                              <span className="text-emerald-400">in {e.days_away as number}d</span>
                            )}
                            {(e.quarter as number) != null && <span>&middot; Q{e.quarter as number} {e.year as number || ""}</span>}
                            {(e.eps_estimate as number) != null && <span>&middot; Est: {e.eps_estimate as number}</span>}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ));
            })()}
          </>
        ) : (
          <p className="text-sm text-muted-foreground">Click &quot;Load Calendar&quot; to see upcoming Indian earnings dates.</p>
        )}
      </div>

      {/* Symbol Input Bar */}
      <div className="rounded-xl border border-border bg-card p-4">
        <div className="flex flex-wrap gap-2 items-center">
          <input
            placeholder="Symbol (e.g. INFY)"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            className="px-3 py-2 rounded-md bg-secondary border border-border text-sm w-36"
          />
          <span className="text-xs text-muted-foreground">Toggle a tool (click again to hide data):</span>
        </div>
      </div>

      {/* ================================================================= */}
      {/* SECTION 2: PREMIUM — Pre-Earnings Analysis Tools */}
      {/* ================================================================= */}
      <div className="rounded-xl border border-amber-500/30 bg-card p-5 space-y-4">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-5 w-5 text-amber-400" />
          <h2 className="text-lg font-semibold">Pre-Earnings Analysis</h2>
          <span className={cn("px-2 py-0.5 rounded-full text-xs border", tierBadge(TIER.Premium))}>Premium</span>
          {tierLevel < 1 && <Lock className="h-4 w-4 text-muted-foreground" />}
        </div>

        {tierLevel < 1 ? (
          <p className="text-sm text-muted-foreground">Upgrade to Premium to access EPS history, pre-earnings profiles, analyst expectations, and options activity.</p>
        ) : (
          <>
            {/* Action buttons row */}
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                aria-pressed={!!openPanels.eps}
                onClick={() => void togglePanel("eps")}
                disabled={panelButtonDisabled("eps")}
                className={panelBtn(!!openPanels.eps, earningsPanelIsPremium("eps"))}
              >
                {isLoading("eps") ? <Spin /> : EARNINGS_PANEL_FETCH.eps.label}
              </button>
              <button
                type="button"
                aria-pressed={!!openPanels.pre}
                onClick={() => void togglePanel("pre")}
                disabled={panelButtonDisabled("pre")}
                className={panelBtn(!!openPanels.pre, earningsPanelIsPremium("pre"))}
              >
                {isLoading("pre") ? <Spin /> : EARNINGS_PANEL_FETCH.pre.label}
              </button>
              <button
                type="button"
                aria-pressed={!!openPanels.expect}
                onClick={() => void togglePanel("expect")}
                disabled={panelButtonDisabled("expect")}
                className={panelBtn(!!openPanels.expect, earningsPanelIsPremium("expect"))}
              >
                {isLoading("expect") ? <Spin /> : EARNINGS_PANEL_FETCH.expect.label}
              </button>
              <button
                type="button"
                aria-pressed={!!openPanels.options}
                onClick={() => void togglePanel("options")}
                disabled={panelButtonDisabled("options")}
                className={panelBtn(!!openPanels.options, earningsPanelIsPremium("options"))}
              >
                {isLoading("options") ? <Spin /> : EARNINGS_PANEL_FETCH.options.label}
              </button>
            </div>

            {/* EPS History */}
            {openPanels.eps && epsHistory && (
              <div className="rounded-lg border border-border p-4 space-y-2">
                <h4 className="font-semibold text-sm flex items-center gap-1"><TrendingUp className="h-3 w-3" /> EPS History: {epsHistory.symbol as string}</h4>
                <p className="text-xs text-muted-foreground">
                  {epsHistory.quarters_available as number} quarters &middot; Avg YoY Growth: {epsHistory.avg_yoy_growth_pct != null ? `${epsHistory.avg_yoy_growth_pct}%` : "—"}
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead className="bg-secondary/50"><tr><th className="p-1.5 text-left">Quarter</th><th className="p-1.5 text-right">EPS</th><th className="p-1.5 text-right">Revenue</th><th className="p-1.5 text-right">QoQ%</th><th className="p-1.5 text-right">YoY%</th></tr></thead>
                    <tbody>
                      {((epsHistory.eps_history as Record<string, unknown>[]) || []).map((q, i) => (
                        <tr key={i} className="border-t border-border">
                          <td className="p-1.5">{q.quarter as string}</td>
                          <td className="p-1.5 text-right font-mono">{q.eps != null ? String(q.eps) : "—"}</td>
                          <td className="p-1.5 text-right font-mono">{q.revenue != null ? Number(q.revenue).toLocaleString() : "—"}</td>
                          <td className={cn("p-1.5 text-right font-mono", (q.qoq_pct as number) > 0 ? "text-emerald-400" : (q.qoq_pct as number) < 0 ? "text-red-400" : "")}>
                            {q.qoq_pct != null ? `${(q.qoq_pct as number) > 0 ? "+" : ""}${q.qoq_pct}%` : "—"}
                          </td>
                          <td className={cn("p-1.5 text-right font-mono", (q.yoy_pct as number) > 0 ? "text-emerald-400" : (q.yoy_pct as number) < 0 ? "text-red-400" : "")}>
                            {q.yoy_pct != null ? `${(q.yoy_pct as number) > 0 ? "+" : ""}${q.yoy_pct}%` : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Pre-Earnings Profile */}
            {openPanels.pre && preProfile && (
              <div className="rounded-lg border border-border p-4 space-y-3">
                <h4 className="font-semibold text-sm flex items-center gap-1"><Target className="h-3 w-3" /> Pre-Earnings Profile: {preProfile.symbol as string}</h4>
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2 text-xs">
                  {Object.entries((preProfile.key_ratios as Record<string, unknown>) || {}).map(([k, v]) => (
                    <div key={k} className="p-2 rounded bg-secondary/50">
                      <span className="text-muted-foreground capitalize">{k.replace(/_/g, " ")}</span>
                      <p className="font-medium font-mono">{v != null ? String(v) : "—"}</p>
                    </div>
                  ))}
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                  <div className="p-2 rounded bg-secondary/50">
                    <span className="text-muted-foreground flex items-center gap-1"><Users className="h-3 w-3" /> FII Trend</span>
                    <p className="font-medium">{(preProfile.shareholding_trend as Record<string, unknown>)?.fii_trend as string || "—"}</p>
                  </div>
                  <div className="p-2 rounded bg-secondary/50">
                    <span className="text-muted-foreground flex items-center gap-1"><Activity className="h-3 w-3" /> Options PCR</span>
                    <p className="font-medium font-mono">{(preProfile.options_activity as Record<string, unknown>)?.pcr != null ? String((preProfile.options_activity as Record<string, unknown>).pcr) : "—"}</p>
                  </div>
                  <div className="p-2 rounded bg-secondary/50">
                    <span className="text-muted-foreground flex items-center gap-1"><Zap className="h-3 w-3" /> News Sentiment</span>
                    <p className={cn("font-medium font-mono", (preProfile.news_sentiment_score as number) > 0 ? "text-emerald-400" : (preProfile.news_sentiment_score as number) < 0 ? "text-red-400" : "")}>
                      {preProfile.news_sentiment_score != null ? String(preProfile.news_sentiment_score) : "—"} ({preProfile.news_articles_count as number || 0} articles)
                    </p>
                  </div>
                </div>
                {/* Last 4 quarters mini-table */}
                {((preProfile.last_4_quarters as Record<string, unknown>[]) || []).length > 0 && (
                  <div className="overflow-x-auto">
                    <p className="text-xs text-muted-foreground mb-1 font-medium">Last 4 Quarters</p>
                    <table className="w-full text-xs">
                      <thead className="bg-secondary/50"><tr><th className="p-1 text-left">Quarter</th><th className="p-1 text-right">EPS</th><th className="p-1 text-right">Revenue</th><th className="p-1 text-right">YoY%</th></tr></thead>
                      <tbody>
                        {((preProfile.last_4_quarters as Record<string, unknown>[]) || []).map((q, i) => (
                          <tr key={i} className="border-t border-border">
                            <td className="p-1">{q.quarter as string}</td>
                            <td className="p-1 text-right font-mono">{q.eps != null ? String(q.eps) : "—"}</td>
                            <td className="p-1 text-right font-mono">{q.revenue != null ? Number(q.revenue).toLocaleString() : "—"}</td>
                            <td className={cn("p-1 text-right font-mono", (q.yoy_pct as number) > 0 ? "text-emerald-400" : "text-red-400")}>{q.yoy_pct != null ? `${q.yoy_pct}%` : "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {/* Analyst Expectations */}
            {openPanels.expect && expectations && (
              <div className="rounded-lg border border-border p-4 space-y-2">
                <h4 className="font-semibold text-sm flex items-center gap-1"><Eye className="h-3 w-3" /> Analyst Expectations: {expectations.symbol as string}</h4>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                  <div className="p-2 rounded bg-secondary/50"><span className="text-muted-foreground">Expected EPS</span><p className="font-medium font-mono">{expectations.consensus_eps != null ? `₹${expectations.consensus_eps}` : "—"}</p></div>
                  <div className="p-2 rounded bg-secondary/50"><span className="text-muted-foreground">Expected Revenue</span><p className="font-medium font-mono">{expectations.consensus_revenue != null ? Number(expectations.consensus_revenue).toLocaleString() : "—"}</p></div>
                  <div className="p-2 rounded bg-secondary/50"><span className="text-muted-foreground">Growth Rate Used</span><p className="font-medium font-mono">{expectations.growth_rate_used_pct != null ? `${expectations.growth_rate_used_pct}%` : "—"}</p></div>
                  <div className="p-2 rounded bg-secondary/50"><span className="text-muted-foreground">Method</span><p className="font-medium">{(expectations.source_type as string) || "—"}</p></div>
                </div>
              </div>
            )}

            {/* Option Chain */}
            {openPanels.options && optionChain && (
              <div className="rounded-lg border border-border p-4 space-y-2">
                <h4 className="font-semibold text-sm flex items-center gap-1"><Activity className="h-3 w-3" /> Option Chain: {optionChain.symbol as string}</h4>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                  <div className="p-2 rounded bg-secondary/50"><span className="text-muted-foreground">Expiry</span><p className="font-medium">{(optionChain.expiry as string) || "—"}</p></div>
                  <div className="p-2 rounded bg-secondary/50"><span className="text-muted-foreground">PCR</span><p className="font-medium font-mono">{optionChain.pcr != null ? String(optionChain.pcr) : "—"}</p></div>
                  <div className="p-2 rounded bg-secondary/50"><span className="text-muted-foreground">Max Pain</span><p className="font-medium font-mono">{optionChain.max_pain != null ? `₹${optionChain.max_pain}` : "—"}</p></div>
                  <div className="p-2 rounded bg-secondary/50"><span className="text-muted-foreground">Call OI / Put OI</span><p className="font-medium font-mono">{optionChain.total_call_oi as number || 0} / {optionChain.total_put_oi as number || 0}</p></div>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* ================================================================= */}
      {/* SECTION 3: PREMIUM — Post-Earnings Analysis */}
      {/* ================================================================= */}
      <div className="rounded-xl border border-amber-500/30 bg-card p-5 space-y-4">
        <div className="flex items-center gap-2">
          <ArrowUpDown className="h-5 w-5 text-amber-400" />
          <h2 className="text-lg font-semibold">Post-Earnings Analysis</h2>
          <span className={cn("px-2 py-0.5 rounded-full text-xs border", tierBadge(TIER.Premium))}>Premium</span>
          {tierLevel < 1 && <Lock className="h-4 w-4 text-muted-foreground" />}
        </div>

        {tierLevel < 1 ? (
          <p className="text-sm text-muted-foreground">Upgrade to Premium to access post-results reaction and beat/miss analysis.</p>
        ) : (
          <>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                aria-pressed={!!openPanels.reaction}
                onClick={() => void togglePanel("reaction")}
                disabled={panelButtonDisabled("reaction")}
                className={panelBtn(!!openPanels.reaction, earningsPanelIsPremium("reaction"))}
              >
                {isLoading("reaction") ? <Spin /> : EARNINGS_PANEL_FETCH.reaction.label}
              </button>
              <button
                type="button"
                aria-pressed={!!openPanels.avse}
                onClick={() => void togglePanel("avse")}
                disabled={panelButtonDisabled("avse")}
                className={panelBtn(!!openPanels.avse, earningsPanelIsPremium("avse"))}
              >
                {isLoading("avse") ? <Spin /> : EARNINGS_PANEL_FETCH.avse.label}
              </button>
            </div>

            {/* Post-Results Reaction */}
            {openPanels.reaction && postReaction && (
              <div className="rounded-lg border border-border p-4 space-y-2">
                <h4 className="font-semibold text-sm">Post-Results Reaction: {postReaction.symbol as string}</h4>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                  <div className="p-2 rounded bg-secondary/50"><span className="text-muted-foreground">Filing Date</span><p className="font-medium">{(postReaction.filing_date as string) || "—"}</p></div>
                  <div className="p-2 rounded bg-secondary/50"><span className="text-muted-foreground">Day 0</span><p className={cn("font-medium font-mono", (postReaction.price_change_day0_pct as number) > 0 ? "text-emerald-400" : "text-red-400")}>{postReaction.price_change_day0_pct != null ? `${postReaction.price_change_day0_pct}%` : "—"}</p></div>
                  <div className="p-2 rounded bg-secondary/50"><span className="text-muted-foreground">Day +1</span><p className={cn("font-medium font-mono", (postReaction.price_change_day1_pct as number) > 0 ? "text-emerald-400" : "text-red-400")}>{postReaction.price_change_day1_pct != null ? `${postReaction.price_change_day1_pct}%` : "—"}</p></div>
                  <div className="p-2 rounded bg-secondary/50"><span className="text-muted-foreground">Day +2</span><p className={cn("font-medium font-mono", (postReaction.price_change_day2_pct as number) > 0 ? "text-emerald-400" : "text-red-400")}>{postReaction.price_change_day2_pct != null ? `${postReaction.price_change_day2_pct}%` : "—"}</p></div>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs">
                  <div className="p-2 rounded bg-secondary/50"><span className="text-muted-foreground">3-Day Cumulative</span><p className="font-medium font-mono">{postReaction.cumulative_3day_pct != null ? `${postReaction.cumulative_3day_pct}%` : "—"}</p></div>
                  <div className="p-2 rounded bg-secondary/50"><span className="text-muted-foreground">Vol Spike</span><p className="font-medium font-mono">{postReaction.volume_spike_pct != null ? `${postReaction.volume_spike_pct}%` : "—"}</p></div>
                  <div className="p-2 rounded bg-secondary/50"><span className="text-muted-foreground">Result Day Volume</span><p className="font-medium font-mono">{postReaction.volume_result_day != null ? Number(postReaction.volume_result_day).toLocaleString() : "—"}</p></div>
                </div>
              </div>
            )}

            {/* Actual vs Expected */}
            {openPanels.avse && actualVsExpected && (
              <div className="rounded-lg border border-border p-4 space-y-2">
                <h4 className="font-semibold text-sm">Beat / Miss: {actualVsExpected.symbol as string}</h4>
                <div className="flex items-center gap-3">
                  <div className={cn("px-4 py-2 rounded-full text-sm font-bold",
                    actualVsExpected.verdict === "beat" ? "bg-emerald-500/20 text-emerald-300" :
                    actualVsExpected.verdict === "miss" ? "bg-red-500/20 text-red-300" :
                    "bg-muted text-muted-foreground"
                  )}>
                    {((actualVsExpected.verdict as string) || "inline").toUpperCase()}
                  </div>
                  <span className="text-sm font-mono">{actualVsExpected.surprise_pct != null ? `${(actualVsExpected.surprise_pct as number) > 0 ? "+" : ""}${actualVsExpected.surprise_pct}%` : "—"} surprise</span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div className="p-2 rounded bg-secondary/50"><span className="text-muted-foreground">Actual EPS</span><p className="font-medium font-mono">{actualVsExpected.actual_eps != null ? `₹${actualVsExpected.actual_eps}` : "—"}</p></div>
                  <div className="p-2 rounded bg-secondary/50"><span className="text-muted-foreground">Expected EPS</span><p className="font-medium font-mono">{actualVsExpected.expected_eps != null ? `₹${actualVsExpected.expected_eps}` : "—"}</p></div>
                  <div className="p-2 rounded bg-secondary/50"><span className="text-muted-foreground">Method</span><p className="font-medium">{(actualVsExpected.estimation_method as string) || "—"}</p></div>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* ================================================================= */}
      {/* SECTION 4: ANALYST — Cross-Source Earnings Verdict */}
      {/* ================================================================= */}
      <div className="rounded-xl border border-purple-500/30 bg-card p-5 space-y-4">
        <div className="flex items-center gap-2">
          <Shield className="h-5 w-5 text-purple-400" />
          <h2 className="text-lg font-semibold">Cross-Source Earnings Verdict</h2>
          <span className={cn("px-2 py-0.5 rounded-full text-xs border", tierBadge(TIER.Analyst))}>Analyst</span>
          {tierLevel < 2 && <Lock className="h-4 w-4 text-muted-foreground" />}
        </div>

        {tierLevel < 2 ? (
          <p className="text-sm text-muted-foreground">Upgrade to Analyst to run the full cross-source earnings verdict combining BSE filings, NSE price data, shareholding, and news sentiment.</p>
        ) : (
          <>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                aria-pressed={!!openPanels.verdict}
                onClick={() => void togglePanel("verdict")}
                disabled={panelButtonDisabled("verdict")}
                className={panelBtn(!!openPanels.verdict, earningsPanelIsPremium("verdict"))}
              >
                {isLoading("verdict") ? <Spin /> : EARNINGS_PANEL_FETCH.verdict.label}
              </button>
              <button
                type="button"
                aria-pressed={!!openPanels.dashboard}
                onClick={() => void togglePanel("dashboard")}
                disabled={panelButtonDisabled("dashboard")}
                className={panelBtn(!!openPanels.dashboard, earningsPanelIsPremium("dashboard"))}
              >
                {isLoading("dashboard") ? <Spin /> : EARNINGS_PANEL_FETCH.dashboard.label}
              </button>
            </div>

            {/* Verdict */}
            {openPanels.verdict && verdict && (
              <div className="rounded-lg border border-border p-4 space-y-3">
                <div className="flex items-center gap-3">
                  <h4 className="font-semibold">Verdict: {verdict.symbol as string}</h4>
                  <div className={cn("px-3 py-1 rounded-full text-sm font-bold",
                    verdict.beat_miss === "beat" ? "bg-emerald-500/20 text-emerald-300" :
                    verdict.beat_miss === "miss" ? "bg-red-500/20 text-red-300" :
                    "bg-muted text-muted-foreground"
                  )}>
                    {((verdict.beat_miss as string) || "inline").toUpperCase()} {verdict.surprise_pct != null ? `(${(verdict.surprise_pct as number) > 0 ? "+" : ""}${verdict.surprise_pct}%)` : ""}
                  </div>
                </div>
                <TrustScorePanel payload={verdict} />
                <p className="text-sm leading-relaxed">{verdict.narrative as string}</p>
                {/* Contradictions */}
                {((verdict.contradictions as string[]) || []).length > 0 && (
                  <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 space-y-1">
                    <p className="text-xs font-semibold text-amber-400 flex items-center gap-1"><AlertTriangle className="h-3 w-3" /> Contradictions Detected</p>
                    {((verdict.contradictions as string[]) || []).map((c, i) => (
                      <p key={i} className="text-xs text-muted-foreground">&bull; {c}</p>
                    ))}
                  </div>
                )}
                {/* Citations */}
                {((verdict.citations as Record<string, unknown>[]) || []).length > 0 && (
                  <div className="text-xs text-muted-foreground space-y-1">
                    <p className="font-medium">Sources &amp; Citations:</p>
                    {((verdict.citations as Record<string, unknown>[]) || []).map((c, i) => (
                      <p key={i}>&bull; [{c.source as string}] {c.data_point as string}</p>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Season Dashboard */}
            {openPanels.dashboard && dashboard && (
              <div className="rounded-lg border border-border p-4 space-y-3">
                <h4 className="font-semibold text-sm flex items-center gap-1"><BarChart3 className="h-3 w-3" /> Earnings Season Dashboard</h4>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                  <div className="p-3 rounded bg-emerald-500/10 text-center"><p className="text-2xl font-bold text-emerald-400">{dashboard.beats as number}</p><p className="text-xs text-muted-foreground">Beats</p></div>
                  <div className="p-3 rounded bg-red-500/10 text-center"><p className="text-2xl font-bold text-red-400">{dashboard.misses as number}</p><p className="text-xs text-muted-foreground">Misses</p></div>
                  <div className="p-3 rounded bg-secondary/50 text-center"><p className="text-2xl font-bold">{dashboard.inlines as number}</p><p className="text-xs text-muted-foreground">Inline</p></div>
                  <div className="p-3 rounded bg-secondary/50 text-center"><p className="text-2xl font-bold">{dashboard.companies_analysed as number}</p><p className="text-xs text-muted-foreground">Analysed</p></div>
                </div>
                {((dashboard.notable_surprises as Record<string, unknown>[]) || []).length > 0 && (
                  <div className="space-y-1">
                    <p className="text-xs font-semibold">Notable Surprises:</p>
                    {((dashboard.notable_surprises as Record<string, unknown>[]) || []).map((s, i) => (
                      <p key={i} className={cn("text-xs", s.type === "positive_surprise" ? "text-emerald-400" : "text-red-400")}>
                        &bull; {s.symbol as string}: {s.type === "positive_surprise" ? "+" : ""}{(s.yoy_growth_pct as number)?.toFixed(1)}% YoY growth
                      </p>
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {/* ================================================================= */}
      {/* SECTION 5: ANALYST — Cross-Company Comparison */}
      {/* ================================================================= */}
      <div className="rounded-xl border border-purple-500/30 bg-card p-5 space-y-4">
        <div className="flex items-center gap-2">
          <FileText className="h-5 w-5 text-purple-400" />
          <h2 className="text-lg font-semibold">Quarterly Performance Comparison</h2>
          <span className={cn("px-2 py-0.5 rounded-full text-xs border", tierBadge(TIER.Analyst))}>Analyst</span>
          {tierLevel < 2 && <Lock className="h-4 w-4 text-muted-foreground" />}
        </div>

        {tierLevel < 2 ? (
          <p className="text-sm text-muted-foreground">Upgrade to Analyst to compare quarterly performance across companies with EPS, ratios, shareholding, and price reaction.</p>
        ) : (
          <>
            <div className="flex gap-2">
              <input value={compareSymbols} onChange={(e) => setCompareSymbols(e.target.value.toUpperCase())} placeholder="TCS,INFY,WIPRO" className="px-3 py-2 rounded-md bg-secondary border border-border text-sm flex-1" />
              <button
                type="button"
                aria-pressed={!!openPanels.compare}
                onClick={() => void togglePanel("compare")}
                disabled={panelButtonDisabled("compare")}
                className={panelBtn(!!openPanels.compare, earningsPanelIsPremium("compare"))}
              >
                {isLoading("compare") ? <Spin /> : EARNINGS_PANEL_FETCH.compare.label}
              </button>
            </div>
            {openPanels.compare && comparison && (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-secondary/50">
                    <tr>
                      <th className="p-2 text-left">Metric</th>
                      {((comparison.symbols as string[]) || []).map((s) => <th key={s} className="p-2 text-right">{s}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {["eps", "revenue", "pe_ratio", "pb_ratio", "roe", "debt_to_equity", "price", "price_change_pct", "eps_yoy_growth_pct", "fii_change_pp"].map((metric) => (
                      <tr key={metric} className="border-t border-border">
                        <td className="p-2 capitalize text-xs">{metric.replace(/_/g, " ")}</td>
                        {((comparison.symbols as string[]) || []).map((s) => {
                          const comp = (comparison.comparison as Record<string, Record<string, unknown>>) || {};
                          const val = comp[s]?.[metric];
                          const isColor = ["price_change_pct", "eps_yoy_growth_pct", "fii_change_pp"].includes(metric);
                          return (
                            <td key={s} className={cn("p-2 text-right font-mono text-xs",
                              isColor && val != null && (val as number) > 0 ? "text-emerald-400" :
                              isColor && val != null && (val as number) < 0 ? "text-red-400" : ""
                            )}>
                              {val != null ? (typeof val === "number" && metric === "revenue" ? Number(val).toLocaleString() : String(val)) : "—"}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
