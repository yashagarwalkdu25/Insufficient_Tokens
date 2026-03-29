"use client";

import { useState } from "react";
import { useSession, signIn } from "next-auth/react";
import { Briefcase, Plus, Trash2, ShieldAlert, AlertTriangle, Loader2, Activity, Lock, TrendingUp, Globe, Newspaper, FileText, Upload } from "lucide-react";
import { callMCPTool } from "@/lib/mcp-client";
import { cn, formatCurrency, formatPercent, tierBadge } from "@/lib/utils";

const TIER_LEVELS: Record<string, number> = { free: 0, premium: 1, analyst: 2 };

interface Holding {
  symbol: string;
  quantity: number;
  avg_price: number;
  current_price?: number;
  current_value?: number;
  pnl?: number;
  pnl_pct?: number;
}

interface RiskAlert {
  alert_type: string;
  severity: string;
  message: string;
}

interface SentimentShift {
  symbol: string;
  sentiment_7d: number;
  direction: string;
}

export default function PortfolioPage() {
  const { data: session, status } = useSession();
  const tier = (session?.tier as string) ?? "free";
  const tierLevel = TIER_LEVELS[tier] ?? 0;
  const token = session?.accessToken;

  const [symbol, setSymbol] = useState("");
  const [qty, setQty] = useState("");
  const [price, setPrice] = useState("");
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [summary, setSummary] = useState<Record<string, unknown> | null>(null);
  const [alerts, setAlerts] = useState<RiskAlert[]>([]);
  const [riskScore, setRiskScore] = useState<number | null>(null);
  const [mfOverlap, setMfOverlap] = useState<Record<string, unknown> | null>(null);
  const [macroSensitivity, setMacroSensitivity] = useState<Record<string, unknown> | null>(null);
  const [sentimentShifts, setSentimentShifts] = useState<SentimentShift[]>([]);
  const [riskReport, setRiskReport] = useState<Record<string, unknown> | null>(null);
  const [whatIfResult, setWhatIfResult] = useState<string>("");
  const [scenario, setScenario] = useState("RBI cuts 25bps");
  const [loading, setLoading] = useState(false);
  const [loadingPremium, setLoadingPremium] = useState(false);
  const [loadingAnalyst, setLoadingAnalyst] = useState(false);
  const [error, setError] = useState("");

  // CSV import state
  const [importPlatform, setImportPlatform] = useState("groww");
  const [importCsv, setImportCsv] = useState("");
  const [importResult, setImportResult] = useState<Record<string, unknown> | null>(null);
  const [loadingImport, setLoadingImport] = useState(false);
  const [showImport, setShowImport] = useState(false);

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
          You must sign in to access the Portfolio Monitor. Your tier determines which tools are available.
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

  async function handleAdd() {
    if (!symbol || !qty || !price) return;
    setLoading(true);
    setError("");
    try {
      const result = await callMCPTool("add_to_portfolio", { symbol: symbol.toUpperCase(), quantity: parseInt(qty), avg_price: parseFloat(price) }, token);
      const raw = result as unknown as Record<string, unknown>;
      if (raw.error) {
        setError(raw.error as string);
        return;
      }
      await refreshPortfolio();
      setSymbol(""); setQty(""); setPrice("");
    } catch { setError("Failed to add to portfolio."); }
    finally { setLoading(false); }
  }

  async function handleRemove(sym: string) {
    setLoading(true);
    try {
      await callMCPTool("remove_from_portfolio", { symbol: sym }, token);
      await refreshPortfolio();
    } catch { setError("Failed to remove."); }
    finally { setLoading(false); }
  }

  async function refreshPortfolio() {
    try {
      const result = await callMCPTool("get_portfolio_summary", {}, token);
      const data = result.data as Record<string, unknown>;
      setHoldings((data.holdings as Holding[]) || []);
      setSummary(data);
    } catch { setError("Failed to load portfolio."); }
  }

  async function handleHealthCheck() {
    setLoading(true); setError("");
    try {
      const result = await callMCPTool("portfolio_health_check", {}, token);
      const data = result.data as Record<string, unknown>;
      setAlerts((data.alerts as RiskAlert[]) || []);
      setRiskScore(data.risk_score as number);
    } catch (e: unknown) {
      const msg = (e as Error).message;
      if (msg === "FORBIDDEN") setError("Health check requires Premium tier.");
      else setError("Failed to run health check.");
    } finally { setLoading(false); }
  }

  async function handlePremiumAnalysis() {
    setLoadingPremium(true); setError("");
    try {
      const [overlapRes, macroRes, sentimentRes] = await Promise.all([
        callMCPTool("check_mf_overlap", {}, token),
        callMCPTool("check_macro_sensitivity", {}, token),
        callMCPTool("detect_sentiment_shift", {}, token),
      ]);
      setMfOverlap(overlapRes.data as Record<string, unknown>);
      setMacroSensitivity(macroRes.data as Record<string, unknown>);
      const sentData = sentimentRes.data as Record<string, unknown>;
      setSentimentShifts((sentData.shifts as SentimentShift[]) || []);
    } catch (e: unknown) {
      const msg = (e as Error).message;
      if (msg === "FORBIDDEN") setError("MF overlap / macro / sentiment requires Premium tier.");
      else setError("Failed to run premium analysis.");
    } finally { setLoadingPremium(false); }
  }

  async function handleRiskReport() {
    setLoadingAnalyst(true); setError("");
    try {
      const result = await callMCPTool("portfolio_risk_report", {}, token);
      const raw = result as unknown as Record<string, unknown>;
      if (raw.error) { setError(raw.error as string); return; }
      setRiskReport(result.data as Record<string, unknown>);
    } catch (e: unknown) {
      const msg = (e as Error).message;
      if (msg === "FORBIDDEN") setError("Risk report requires Analyst tier.");
      else setError("Failed to generate risk report.");
    } finally { setLoadingAnalyst(false); }
  }

  async function handleWhatIf() {
    setLoadingAnalyst(true); setError("");
    try {
      const result = await callMCPTool("what_if_analysis", { scenario }, token);
      const data = result.data as Record<string, unknown>;
      setWhatIfResult(data.narrative as string);
    } catch (e: unknown) {
      const msg = (e as Error).message;
      if (msg === "FORBIDDEN") setError("What-if analysis requires Analyst tier.");
      else setError("Failed to run scenario analysis.");
    } finally { setLoadingAnalyst(false); }
  }

  async function handleImportCsv() {
    if (!importCsv.trim()) return;
    setLoadingImport(true);
    setError("");
    setImportResult(null);
    try {
      const result = await callMCPTool("import_portfolio", {
        holdings_csv: importCsv,
        platform: importPlatform,
      }, token);
      const raw = result as unknown as Record<string, unknown>;
      if (raw.error) {
        setError(raw.error as string);
        return;
      }
      setImportResult(result.data as Record<string, unknown>);
      await refreshPortfolio();
      setImportCsv("");
    } catch { setError("Failed to import portfolio."); }
    finally { setLoadingImport(false); }
  }

  function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      setImportCsv((ev.target?.result as string) || "");
    };
    reader.readAsText(file);
  }

  const anyLoading = loading || loadingPremium || loadingAnalyst || loadingImport;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2"><Briefcase className="h-6 w-6" /> Portfolio Monitor</h1>
          <p className="text-muted-foreground text-sm">Track holdings, detect risks, simulate scenarios</p>
        </div>
        <span className={cn("px-2 py-0.5 rounded-full text-xs font-medium border uppercase", tierBadge(tier))}>{tier}</span>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 shrink-0" /> {error}
        </div>
      )}

      {/* ═══ SECTION 1 — FREE: Add/Remove Holdings + Summary ═══ */}
      <div className="rounded-xl border border-border bg-card p-4 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold flex items-center gap-2"><Plus className="h-4 w-4" /> Add Holding</h3>
          <span className={cn("px-2 py-0.5 rounded-full text-xs border", tierBadge("free"))}>Free</span>
        </div>
        <div className="flex flex-wrap gap-2">
          <input placeholder="Symbol" value={symbol} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSymbol(e.target.value.toUpperCase())} className="px-3 py-2 rounded-md bg-secondary border border-border text-sm w-32" />
          <input placeholder="Qty" type="number" value={qty} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setQty(e.target.value)} className="px-3 py-2 rounded-md bg-secondary border border-border text-sm w-20" />
          <input placeholder="Avg Price" type="number" value={price} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPrice(e.target.value)} className="px-3 py-2 rounded-md bg-secondary border border-border text-sm w-28" />
          <button onClick={handleAdd} disabled={anyLoading} className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50">
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Add"}
          </button>
          <button onClick={refreshPortfolio} disabled={anyLoading} className="px-4 py-2 rounded-md bg-secondary text-sm hover:bg-secondary/80 disabled:opacity-50">Refresh</button>
        </div>
      </div>

      {/* ═══ Import from Groww / Zerodha / Angel One ═══ */}
      <div className="rounded-xl border border-border bg-card p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold flex items-center gap-2"><Upload className="h-4 w-4" /> Import from Broker</h3>
          <button onClick={() => setShowImport(!showImport)} className="px-3 py-1.5 rounded-md bg-secondary text-xs hover:bg-secondary/80">
            {showImport ? "Hide" : "Import CSV"}
          </button>
        </div>
        {showImport && (
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">
              Export your holdings as CSV from <strong>Groww</strong>, <strong>Zerodha (Kite)</strong>, or <strong>Angel One</strong>, then upload or paste below.
            </p>
            <div className="flex flex-wrap gap-2 items-center">
              <select
                value={importPlatform}
                onChange={(e) => setImportPlatform(e.target.value)}
                className="px-3 py-2 rounded-md bg-secondary border border-border text-sm"
              >
                <option value="groww">Groww</option>
                <option value="zerodha">Zerodha (Kite)</option>
                <option value="angelone">Angel One</option>
                <option value="generic">Generic CSV</option>
              </select>
              <label className="px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-medium cursor-pointer hover:bg-primary/90">
                Choose File
                <input type="file" accept=".csv,.txt" onChange={handleFileUpload} className="hidden" />
              </label>
              {importCsv && <span className="text-xs text-emerald-400">CSV loaded ({importCsv.split("\n").length - 1} rows)</span>}
            </div>
            <textarea
              value={importCsv}
              onChange={(e) => setImportCsv(e.target.value)}
              placeholder={"Symbol,Quantity,Avg Cost\nRELIANCE,10,2450.50\nTCS,5,3500.00\nINFY,20,1420.75"}
              rows={5}
              className="w-full px-3 py-2 rounded-md bg-secondary border border-border text-xs font-mono resize-y"
            />
            <button
              onClick={handleImportCsv}
              disabled={anyLoading || !importCsv.trim()}
              className="px-4 py-2 rounded-md bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-500 disabled:opacity-50"
            >
              {loadingImport ? <Loader2 className="h-4 w-4 animate-spin inline mr-1" /> : <Upload className="h-3 w-3 inline mr-1" />}
              Import Holdings
            </button>
            {importResult && (
              <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm space-y-1">
                <p className="text-emerald-300 font-medium">
                  Imported {importResult.imported_count as number} holdings from {importResult.platform as string}
                  {(importResult.skipped_count as number) > 0 && (
                    <span className="text-amber-400"> ({importResult.skipped_count as number} skipped)</span>
                  )}
                </p>
                {((importResult.skipped as Record<string, unknown>[]) || []).length > 0 && (
                  <div className="text-xs text-muted-foreground">
                    <p className="font-medium text-amber-400">Skipped:</p>
                    {((importResult.skipped as Record<string, unknown>[]) || []).map((s, i) => (
                      <p key={i}>&bull; {s.symbol as string}: {s.reason as string}</p>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Holdings Table */}
      {holdings.length > 0 && (
        <div className="rounded-xl border border-border bg-card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-secondary/50">
              <tr>
                <th className="text-left p-3 font-medium">Symbol</th>
                <th className="text-right p-3 font-medium">Qty</th>
                <th className="text-right p-3 font-medium">Avg Price</th>
                <th className="text-right p-3 font-medium">Current</th>
                <th className="text-right p-3 font-medium">P&L</th>
                <th className="text-right p-3 font-medium">P&L %</th>
                <th className="text-right p-3 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {holdings.map((h: Holding) => (
                <tr key={h.symbol} className="border-t border-border">
                  <td className="p-3 font-medium">{h.symbol}</td>
                  <td className="p-3 text-right">{h.quantity}</td>
                  <td className="p-3 text-right">{formatCurrency(h.avg_price)}</td>
                  <td className="p-3 text-right">{formatCurrency(h.current_price)}</td>
                  <td className={cn("p-3 text-right font-medium", (h.pnl || 0) >= 0 ? "text-emerald-400" : "text-red-400")}>{formatCurrency(h.pnl)}</td>
                  <td className={cn("p-3 text-right", (h.pnl_pct || 0) >= 0 ? "text-emerald-400" : "text-red-400")}>{formatPercent(h.pnl_pct)}</td>
                  <td className="p-3 text-right"><button onClick={() => handleRemove(h.symbol)} className="text-muted-foreground hover:text-destructive"><Trash2 className="h-4 w-4" /></button></td>
                </tr>
              ))}
            </tbody>
          </table>
          {summary && (
            <div className="p-4 border-t border-border flex flex-wrap gap-6 text-sm">
              <div><span className="text-muted-foreground">Invested</span><p className="font-bold">{formatCurrency(summary.total_invested as number)}</p></div>
              <div><span className="text-muted-foreground">Current Value</span><p className="font-bold">{formatCurrency(summary.current_value as number)}</p></div>
              <div><span className="text-muted-foreground">Total P&L</span><p className={cn("font-bold", (summary.total_pnl as number || 0) >= 0 ? "text-emerald-400" : "text-red-400")}>{formatCurrency(summary.total_pnl as number)} ({formatPercent(summary.total_pnl_pct as number)})</p></div>
            </div>
          )}
        </div>
      )}

      {/* ═══ SECTION 2 — PREMIUM: Health Check + Concentration Risk ═══ */}
      {holdings.length > 0 && (
        <div className={cn("rounded-xl border bg-card p-4 space-y-3", tierLevel >= 1 ? "border-emerald-500/30" : "border-border opacity-60")}>
          <div className="flex items-center justify-between">
            <h3 className="font-semibold flex items-center gap-2"><ShieldAlert className="h-4 w-4 text-emerald-400" /> Health Check &amp; Concentration Risk</h3>
            <div className="flex items-center gap-2">
              <span className={cn("px-2 py-0.5 rounded-full text-xs border", tierBadge("premium"))}>Premium+</span>
              {tierLevel >= 1 ? (
                <button onClick={handleHealthCheck} disabled={anyLoading} className="px-3 py-1.5 rounded-md bg-emerald-600 text-white text-xs font-medium hover:bg-emerald-500 disabled:opacity-50">
                  {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : "Run Check"}
                </button>
              ) : (
                <span className="flex items-center gap-1 text-xs text-muted-foreground"><Lock className="h-3 w-3" /> Upgrade to Premium</span>
              )}
            </div>
          </div>

          {tierLevel < 1 && (
            <p className="text-xs text-muted-foreground">Checks for single-stock concentration (&gt;20%) and sector over-exposure (&gt;40%). Upgrade to Premium to unlock.</p>
          )}

          {riskScore !== null && (
            <p className="text-sm">Risk Score: <span className={cn("font-bold text-lg", riskScore > 50 ? "text-red-400" : riskScore > 25 ? "text-amber-400" : "text-emerald-400")}>{riskScore}/100</span></p>
          )}
          {alerts.map((a: RiskAlert, i: number) => (
            <div key={i} className={cn("rounded-lg p-3 text-sm border", a.severity === "high" ? "border-red-500/30 bg-red-500/10 text-red-300" : "border-amber-500/30 bg-amber-500/10 text-amber-300")}>
              <span className="font-medium uppercase text-xs">{a.alert_type}</span>: {a.message}
            </div>
          ))}
          {riskScore !== null && alerts.length === 0 && (
            <p className="text-sm text-emerald-400">No concentration or sector risk flags detected.</p>
          )}
        </div>
      )}

      {/* ═══ SECTION 3 — PREMIUM: MF Overlap + Macro Sensitivity + Sentiment ═══ */}
      {holdings.length > 0 && (
        <div className={cn("rounded-xl border bg-card p-4 space-y-4", tierLevel >= 1 ? "border-amber-500/30" : "border-border opacity-60")}>
          <div className="flex items-center justify-between">
            <h3 className="font-semibold flex items-center gap-2"><TrendingUp className="h-4 w-4 text-amber-400" /> Risk Intelligence</h3>
            <div className="flex items-center gap-2">
              <span className={cn("px-2 py-0.5 rounded-full text-xs border", tierBadge("premium"))}>Premium+</span>
              {tierLevel >= 1 ? (
                <button onClick={handlePremiumAnalysis} disabled={anyLoading} className="px-3 py-1.5 rounded-md bg-amber-600 text-white text-xs font-medium hover:bg-amber-500 disabled:opacity-50">
                  {loadingPremium ? <Loader2 className="h-3 w-3 animate-spin" /> : "Run Analysis"}
                </button>
              ) : (
                <span className="flex items-center gap-1 text-xs text-muted-foreground"><Lock className="h-3 w-3" /> Upgrade to Premium</span>
              )}
            </div>
          </div>

          {tierLevel < 1 && (
            <p className="text-xs text-muted-foreground">Includes MF overlap detection, macro sensitivity mapping, and sentiment shift detection. Upgrade to Premium to unlock.</p>
          )}

          {/* MF Overlap */}
          {mfOverlap && (
            <div className="space-y-2">
              <p className="text-xs font-medium text-amber-300 flex items-center gap-1"><Globe className="h-3 w-3" /> Mutual Fund Overlap</p>
              <p className="text-sm">{mfOverlap.message as string}</p>
              {((mfOverlap.overlapping_with_top_mf as string[]) || []).length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {((mfOverlap.overlapping_with_top_mf as string[]) || []).map((s: string) => (
                    <span key={s} className="px-2 py-0.5 bg-amber-500/20 text-amber-300 rounded text-xs font-mono">{s}</span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Macro Sensitivity */}
          {macroSensitivity && (
            <div className="space-y-2">
              <p className="text-xs font-medium text-amber-300 flex items-center gap-1"><TrendingUp className="h-3 w-3" /> Macro Sensitivity</p>
              <div className="grid grid-cols-3 gap-2 text-sm">
                <div className="p-2 rounded-lg bg-secondary/50"><span className="text-muted-foreground text-xs">Repo Rate</span><p className="font-mono font-medium">{(macroSensitivity.repo_rate as number) ?? "—"}%</p></div>
                <div className="p-2 rounded-lg bg-secondary/50"><span className="text-muted-foreground text-xs">CPI</span><p className="font-mono font-medium">{(macroSensitivity.cpi as number) ?? "—"}%</p></div>
                <div className="p-2 rounded-lg bg-secondary/50"><span className="text-muted-foreground text-xs">USD/INR</span><p className="font-mono font-medium">{(macroSensitivity.usd_inr as number) ?? "—"}</p></div>
              </div>
              {((macroSensitivity.macro_impacts as string[]) || []).map((m: string, i: number) => (
                <p key={i} className="text-sm text-amber-200 bg-amber-500/10 rounded-lg p-2 border border-amber-500/20">{m}</p>
              ))}
            </div>
          )}

          {/* Sentiment Shifts */}
          {sentimentShifts.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-medium text-amber-300 flex items-center gap-1"><Newspaper className="h-3 w-3" /> Sentiment Shifts (7-day)</p>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                {sentimentShifts.map((s: SentimentShift) => (
                  <div key={s.symbol} className="p-2 rounded-lg bg-secondary/50">
                    <span className="font-mono font-medium">{s.symbol}</span>
                    <p className={cn("text-xs", s.direction === "positive" ? "text-emerald-400" : "text-red-400")}>{s.direction} ({s.sentiment_7d})</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ═══ SECTION 4 — ANALYST: Full Risk Report ═══ */}
      {holdings.length > 0 && (
        <div className={cn("rounded-xl border bg-card p-4 space-y-4", tierLevel >= 2 ? "border-purple-500/30" : "border-border opacity-60")}>
          <div className="flex items-center justify-between">
            <h3 className="font-semibold flex items-center gap-2"><FileText className="h-4 w-4 text-purple-400" /> Cross-Source Risk Report</h3>
            <div className="flex items-center gap-2">
              <span className={cn("px-2 py-0.5 rounded-full text-xs border", tierBadge("analyst"))}>Analyst Only</span>
              {tierLevel >= 2 ? (
                <button onClick={handleRiskReport} disabled={anyLoading} className="px-3 py-1.5 rounded-md bg-purple-600 text-white text-xs font-medium hover:bg-purple-500 disabled:opacity-50">
                  {loadingAnalyst ? <Loader2 className="h-3 w-3 animate-spin" /> : "Generate Report"}
                </button>
              ) : (
                <span className="flex items-center gap-1 text-xs text-muted-foreground"><Lock className="h-3 w-3" /> Upgrade to Analyst</span>
              )}
            </div>
          </div>

          {tierLevel < 2 && (
            <p className="text-xs text-muted-foreground">Full cross-source risk analysis combining NSE prices, RBI macro, news sentiment, and MF overlap into a single risk narrative with citations.</p>
          )}

          {riskReport && (
            <div className="space-y-3">
              {(riskReport.narrative as string) && (
                <div className="p-3 rounded-lg bg-purple-500/10 border border-purple-500/20 text-sm whitespace-pre-wrap">{riskReport.narrative as string}</div>
              )}
              {((riskReport.citations as {source: string; data_point: string}[]) || []).length > 0 && (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-purple-300">Citations</p>
                  {((riskReport.citations as {source: string; data_point: string}[]) || []).map((c: {source: string; data_point: string}, i: number) => (
                    <p key={i} className="text-xs text-muted-foreground">[{c.source}] {c.data_point}</p>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ═══ SECTION 5 — ANALYST: What-If Simulator ═══ */}
      {holdings.length > 0 && (
        <div className={cn("rounded-xl border bg-card p-4 space-y-3", tierLevel >= 2 ? "border-purple-500/30" : "border-border opacity-60")}>
          <div className="flex items-center justify-between">
            <h3 className="font-semibold flex items-center gap-2"><Activity className="h-4 w-4 text-purple-400" /> What-If Simulator</h3>
            <div className="flex items-center gap-2">
              <span className={cn("px-2 py-0.5 rounded-full text-xs border", tierBadge("analyst"))}>Analyst Only</span>
            </div>
          </div>

          {tierLevel >= 2 ? (
            <div className="flex gap-2">
              <select value={scenario} onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setScenario(e.target.value)} className="px-3 py-2 rounded-md bg-secondary border border-border text-sm flex-1">
                <option>RBI cuts 25bps</option>
                <option>USD/INR +5%</option>
                <option>IT sector correction 10%</option>
                <option>Crude oil +20%</option>
              </select>
              <button onClick={handleWhatIf} disabled={anyLoading} className="px-3 py-1.5 rounded-md bg-purple-600 text-white text-xs font-medium hover:bg-purple-500 disabled:opacity-50">
                {loadingAnalyst ? <Loader2 className="h-3 w-3 animate-spin" /> : "Simulate"}
              </button>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground flex items-center gap-1"><Lock className="h-3 w-3" /> Simulate rate changes, currency moves, sector corrections. Analyst tier only.</p>
          )}
          {whatIfResult && <p className="text-sm bg-purple-500/10 border border-purple-500/20 rounded-lg p-3">{whatIfResult}</p>}
        </div>
      )}
    </div>
  );
}
