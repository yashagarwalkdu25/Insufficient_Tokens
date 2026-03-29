"use client";

import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { Settings, ArrowUpCircle, CheckCircle2, Server, Loader2, Shield, Zap, Crown, Check, X } from "lucide-react";
import { getServerStatus, getHealthCheck } from "@/lib/mcp-client";
import { cn, tierBadge } from "@/lib/utils";

const TIER_FEATURES = [
  {
    category: "Research Copilot (PS1)",
    features: [
      { name: "Stock quotes & price history", free: true, premium: true, analyst: true },
      { name: "Company & market news", free: true, premium: true, analyst: true },
      { name: "Mutual fund NAV lookup", free: true, premium: true, analyst: true },
      { name: "Index data & gainers/losers", free: true, premium: true, analyst: true },
      { name: "Fundamental ratios & financials", free: false, premium: true, analyst: true },
      { name: "Technical indicators (RSI, SMA, MACD)", free: false, premium: true, analyst: true },
      { name: "Shareholding patterns", free: false, premium: true, analyst: true },
      { name: "News sentiment analysis", free: false, premium: true, analyst: true },
      { name: "Cross-source signal matrix", free: false, premium: false, analyst: true },
      { name: "AI research brief generation", free: false, premium: false, analyst: true },
    ],
  },
  {
    category: "Portfolio Monitor (PS2)",
    features: [
      { name: "Add/remove holdings", free: true, premium: true, analyst: true },
      { name: "Portfolio summary & value", free: true, premium: true, analyst: true },
      { name: "Health check & concentration risk", free: true, premium: true, analyst: true },
      { name: "Mutual fund overlap detection", free: false, premium: true, analyst: true },
      { name: "Macro sensitivity analysis", free: false, premium: true, analyst: true },
      { name: "Sentiment shift detection", free: false, premium: true, analyst: true },
      { name: "AI portfolio risk report", free: false, premium: false, analyst: true },
      { name: "What-if scenario simulation", free: false, premium: false, analyst: true },
    ],
  },
  {
    category: "Earnings Command Center (PS3)",
    features: [
      { name: "Upcoming earnings calendar", free: true, premium: true, analyst: true },
      { name: "Historical results dates", free: true, premium: true, analyst: true },
      { name: "EPS history with YoY/QoQ trends", free: false, premium: true, analyst: true },
      { name: "Pre-earnings profile (4Q + options + FII)", free: false, premium: true, analyst: true },
      { name: "Analyst expectations (extrapolated)", free: false, premium: true, analyst: true },
      { name: "Post-results price reaction", free: false, premium: true, analyst: true },
      { name: "Beat/miss analysis", free: false, premium: true, analyst: true },
      { name: "Option chain (OI, IV, PCR, max pain)", free: false, premium: true, analyst: true },
      { name: "Cross-source earnings verdict", free: false, premium: false, analyst: true },
      { name: "Earnings season dashboard", free: false, premium: false, analyst: true },
      { name: "Cross-company quarterly comparison", free: false, premium: false, analyst: true },
      { name: "Filing document access", free: false, premium: false, analyst: true },
      { name: "AI quarterly filing parsing", free: false, premium: false, analyst: true },
    ],
  },
];

const TIER_META = [
  { key: "free", label: "Free", icon: Shield, color: "border-emerald-500/50 bg-emerald-500/5", badge: "text-emerald-400 border-emerald-500/50", rate: "30 calls/hr", demo: "free_user / free123", tools: 14 },
  { key: "premium", label: "Premium", icon: Zap, color: "border-blue-500/50 bg-blue-500/5", badge: "text-blue-400 border-blue-500/50", rate: "150 calls/hr", demo: "premium_user / premium123", tools: 30 },
  { key: "analyst", label: "Analyst", icon: Crown, color: "border-amber-500/50 bg-amber-500/5", badge: "text-amber-400 border-amber-500/50", rate: "500 calls/hr", demo: "analyst_user / analyst123", tools: 44 },
];

export default function SettingsPage() {
  const { data: session } = useSession();
  const tier = (session?.tier as string) ?? "free";

  const [serverHealth, setServerHealth] = useState<string>("unknown");
  const [apiStatus, setApiStatus] = useState<Record<string, unknown> | null>(null);
  const [requestedTier, setRequestedTier] = useState("");
  const [requestStatus, setRequestStatus] = useState<"idle" | "submitting" | "submitted" | "error">("idle");

  useEffect(() => {
    getHealthCheck()
      .then((h) => setServerHealth(h.status))
      .catch(() => setServerHealth("offline"));
    getServerStatus()
      .then(setApiStatus)
      .catch(() => null);
  }, []);

  async function handleUpgradeRequest() {
    if (!requestedTier) return;
    setRequestStatus("submitting");
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_MCP_SERVER_URL || "http://localhost:10004"}/api/tier-request`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(session?.accessToken
              ? { Authorization: `Bearer ${session.accessToken}` }
              : {}),
          },
          body: JSON.stringify({ requested_tier: requestedTier }),
        }
      );
      if (res.ok) setRequestStatus("submitted");
      else setRequestStatus("error");
    } catch { setRequestStatus("error"); }
  }

  const upgradeTiers = tier === "free" ? ["premium", "analyst"] : tier === "premium" ? ["analyst"] : [];

  return (
    <div className="space-y-8 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2"><Settings className="h-6 w-6" /> Settings</h1>
        <p className="text-muted-foreground">Account, server status, and tier management</p>
      </div>

      {/* Account Info */}
      <div className="rounded-xl border border-border bg-card p-6 space-y-4">
        <h3 className="font-semibold">Account</h3>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-muted-foreground">Name</span>
            <p className="font-medium">{session?.user?.name || "—"}</p>
          </div>
          <div>
            <span className="text-muted-foreground">Email</span>
            <p className="font-medium">{session?.user?.email || "—"}</p>
          </div>
          <div>
            <span className="text-muted-foreground">Current Tier</span>
            <p><span className={cn("px-2 py-0.5 rounded-full text-xs font-medium border uppercase", tierBadge(tier))}>{tier}</span></p>
          </div>
        </div>
      </div>

      {/* Tier Upgrade Request */}
      {upgradeTiers.length > 0 && (
        <div className="rounded-xl border border-border bg-card p-6 space-y-4">
          <h3 className="font-semibold flex items-center gap-2"><ArrowUpCircle className="h-4 w-4" /> Request Tier Upgrade</h3>
          <p className="text-sm text-muted-foreground">Submit a request to upgrade your tier. An admin will review and approve.</p>
          <div className="flex gap-2">
            <select
              value={requestedTier}
              onChange={(e) => setRequestedTier(e.target.value)}
              className="px-3 py-2 rounded-md bg-secondary border border-border text-sm"
            >
              <option value="">Select tier...</option>
              {upgradeTiers.map((t) => <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>)}
            </select>
            <button
              onClick={handleUpgradeRequest}
              disabled={!requestedTier || requestStatus === "submitting"}
              className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
            >
              {requestStatus === "submitting" ? <Loader2 className="h-4 w-4 animate-spin" /> : "Submit Request"}
            </button>
          </div>
          {requestStatus === "submitted" && (
            <p className="text-sm text-emerald-400 flex items-center gap-1"><CheckCircle2 className="h-4 w-4" /> Request submitted. Awaiting admin approval.</p>
          )}
          {requestStatus === "error" && (
            <p className="text-sm text-destructive">Failed to submit request.</p>
          )}
        </div>
      )}

      {/* Tiered Access Comparison — Cards */}
      <div>
        <h2 className="text-xl font-bold text-center mb-6">Tiered Access</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {TIER_META.map((t) => {
            const Icon = t.icon;
            const isCurrent = tier === t.key;
            return (
              <div key={t.key} className={cn("rounded-xl border p-5 space-y-4 relative", t.color, isCurrent && "ring-2 ring-primary")}>
                {isCurrent && (
                  <span className="absolute -top-2.5 left-1/2 -translate-x-1/2 bg-primary text-primary-foreground text-[10px] font-bold px-2 py-0.5 rounded-full uppercase">Current</span>
                )}
                <div className="flex items-center gap-2">
                  <Icon className="h-5 w-5" />
                  <span className={cn("px-2.5 py-0.5 rounded-full text-xs font-bold border uppercase tracking-wider", t.badge)}>{t.label}</span>
                </div>
                <div className="text-xs text-muted-foreground space-y-1">
                  <p><span className="font-medium text-foreground">{t.tools}</span> MCP tools</p>
                  <p><span className="font-medium text-foreground">{t.rate}</span> rate limit</p>
                </div>
                <p className="text-[11px] font-mono text-muted-foreground">Demo: {t.demo}</p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Feature Comparison Table */}
      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-secondary/30">
                <th className="text-left p-3 font-semibold">Feature</th>
                <th className="text-center p-3 font-semibold w-20">
                  <span className="text-emerald-400">Free</span>
                </th>
                <th className="text-center p-3 font-semibold w-20">
                  <span className="text-blue-400">Premium</span>
                </th>
                <th className="text-center p-3 font-semibold w-20">
                  <span className="text-amber-400">Analyst</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {TIER_FEATURES.map((cat) => (
                <>
                  <tr key={cat.category} className="border-t border-border bg-secondary/10">
                    <td colSpan={4} className="p-2.5 font-semibold text-xs uppercase tracking-wider text-muted-foreground">
                      {cat.category}
                    </td>
                  </tr>
                  {cat.features.map((f) => (
                    <tr key={f.name} className="border-t border-border/50 hover:bg-secondary/20 transition-colors">
                      <td className="p-2.5 text-xs">{f.name}</td>
                      <td className="p-2.5 text-center">
                        {f.free
                          ? <Check className="h-4 w-4 text-emerald-400 mx-auto" />
                          : <X className="h-4 w-4 text-muted-foreground/30 mx-auto" />}
                      </td>
                      <td className="p-2.5 text-center">
                        {f.premium
                          ? <Check className="h-4 w-4 text-blue-400 mx-auto" />
                          : <X className="h-4 w-4 text-muted-foreground/30 mx-auto" />}
                      </td>
                      <td className="p-2.5 text-center">
                        {f.analyst
                          ? <Check className="h-4 w-4 text-amber-400 mx-auto" />
                          : <X className="h-4 w-4 text-muted-foreground/30 mx-auto" />}
                      </td>
                    </tr>
                  ))}
                </>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Server Status */}
      <div className="rounded-xl border border-border bg-card p-6 space-y-4">
        <h3 className="font-semibold flex items-center gap-2"><Server className="h-4 w-4" /> MCP Server Status</h3>
        <div className="flex items-center gap-2 text-sm">
          <span className={cn("h-2.5 w-2.5 rounded-full", serverHealth === "ok" || serverHealth === "healthy" ? "bg-emerald-400" : "bg-red-400")} />
          {serverHealth === "ok" || serverHealth === "healthy" ? "Connected" : serverHealth === "offline" ? "Offline" : "Checking..."}
        </div>
        {apiStatus && (
          <div className="space-y-1 text-sm">
            <p className="text-muted-foreground font-medium">Upstream APIs:</p>
            {Object.entries(apiStatus).map(([name, status]) => (
              <div key={name} className="flex items-center justify-between px-3 py-1.5 rounded bg-secondary/50">
                <span className="capitalize">{name.replace(/_/g, " ")}</span>
                <span className={cn("text-xs", status === "healthy" ? "text-emerald-400" : "text-amber-400")}>{String(status)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
