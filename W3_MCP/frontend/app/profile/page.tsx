"use client";

import { useSession, signOut } from "next-auth/react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  User,
  Shield,
  Key,
  Layers,
  ArrowUpCircle,
  LogOut,
  CheckCircle2,
  Clock,
} from "lucide-react";
import { cn, tierBadge, TIER_CONFIG, type Tier } from "@/lib/utils";

const SCOPE_LABELS: Record<string, string> = {
  "market:read": "Market Data",
  "mf:read": "Mutual Funds",
  "news:read": "News",
  "watchlist:read": "Watchlist (Read)",
  "watchlist:write": "Watchlist (Write)",
  "fundamentals:read": "Fundamentals",
  "technicals:read": "Technical Indicators",
  "macro:read": "Macro Data",
  "portfolio:read": "Portfolio (Read)",
  "portfolio:write": "Portfolio (Write)",
  "filings:read": "Filings",
  "filings:deep": "Deep Filing Analysis",
  "macro:historical": "Historical Macro",
  "research:generate": "AI Research Generation",
};

export default function ProfilePage() {
  const { data: session, status } = useSession();
  const router = useRouter();

  if (status === "loading") {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="animate-pulse text-muted-foreground">Loading profile...</div>
      </div>
    );
  }

  if (!session) {
    router.push("/");
    return null;
  }

  const user = session.user;
  const tier = (user?.tier || "free") as Tier;
  const roles: string[] = user?.roles || [];
  const scopes: string[] = user?.scopes || [];
  const tierConfig = TIER_CONFIG[tier] || TIER_CONFIG.free;

  const allTiers: Tier[] = ["free", "premium", "analyst", "admin"];
  const currentTierIndex = allTiers.indexOf(tier);

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <User className="h-6 w-6" /> User Profile
          </h1>
          <p className="text-muted-foreground text-sm">Your account details and access level</p>
        </div>
        <button
          onClick={() => signOut()}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
        >
          <LogOut className="h-4 w-4" /> Sign Out
        </button>
      </div>

      {/* User Info Card */}
      <div className="rounded-xl border border-border bg-card p-6 space-y-4">
        <div className="flex items-center gap-4">
          <div className="h-14 w-14 rounded-full bg-primary/20 flex items-center justify-center">
            <User className="h-7 w-7 text-primary" />
          </div>
          <div className="space-y-1">
            <h2 className="text-lg font-semibold">{user?.name || "Unknown User"}</h2>
            <p className="text-sm text-muted-foreground">{user?.email || "—"}</p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 pt-2 border-t border-border">
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">User ID</p>
            <p className="text-sm font-mono text-muted-foreground/80 truncate">{user?.id || "—"}</p>
          </div>
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">Roles</p>
            <div className="flex flex-wrap gap-1">
              {roles.length > 0 ? roles.map((role) => (
                <span key={role} className="px-1.5 py-0.5 rounded text-xs bg-secondary border border-border">
                  {role}
                </span>
              )) : <span className="text-sm text-muted-foreground/60">—</span>}
            </div>
          </div>
        </div>
      </div>

      {/* Current Plan Card */}
      <div className="rounded-xl border border-border bg-card p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold flex items-center gap-2">
            <Layers className="h-4 w-4" /> Current Plan
          </h3>
          {tier !== "admin" && tier !== "analyst" && (
            <Link
              href="/settings"
              className="flex items-center gap-1 text-xs text-primary hover:underline"
            >
              <ArrowUpCircle className="h-3 w-3" /> Request Upgrade
            </Link>
          )}
        </div>

        {/* Tier Progress */}
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <span
              className={cn(
                "px-3 py-1 rounded-full text-sm font-semibold border uppercase tracking-wide",
                tierBadge(tier)
              )}
            >
              {tier}
            </span>
            <span className="text-sm text-muted-foreground">
              {tierConfig.rateLimit} requests/min
            </span>
          </div>

          {/* Visual Tier Indicator */}
          <div className="flex gap-1">
            {allTiers.filter(t => t !== "admin").map((t, i) => (
              <div
                key={t}
                className={cn(
                  "h-2 flex-1 rounded-full transition-colors",
                  i <= currentTierIndex
                    ? t === "free"
                      ? "bg-emerald-500"
                      : t === "premium"
                      ? "bg-amber-500"
                      : "bg-purple-500"
                    : "bg-secondary"
                )}
              />
            ))}
          </div>
          <div className="flex justify-between text-[10px] text-muted-foreground uppercase tracking-wider">
            {allTiers.filter(t => t !== "admin").map((t) => (
              <span key={t} className={cn(t === tier && "text-foreground font-medium")}>
                {t}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Access Scopes Card */}
      <div className="rounded-xl border border-border bg-card p-6 space-y-4">
        <h3 className="font-semibold flex items-center gap-2">
          <Key className="h-4 w-4" /> Access Scopes ({scopes.length})
        </h3>
        <div className="grid grid-cols-2 gap-2">
          {scopes.map((scope) => (
            <div
              key={scope}
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-secondary/50 border border-border text-sm"
            >
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
              <span className="truncate">{SCOPE_LABELS[scope] || scope}</span>
            </div>
          ))}
        </div>

        {/* Locked Scopes */}
        {tier !== "admin" && tier !== "analyst" && (
          <div className="pt-3 border-t border-border space-y-2">
            <p className="text-xs text-muted-foreground font-medium">Locked scopes (upgrade to unlock):</p>
            <div className="grid grid-cols-2 gap-2">
              {Object.keys(SCOPE_LABELS)
                .filter((s) => !scopes.includes(s))
                .map((scope) => (
                  <div
                    key={scope}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg bg-secondary/20 border border-border/50 text-sm text-muted-foreground/50"
                  >
                    <Clock className="h-3.5 w-3.5 shrink-0" />
                    <span className="truncate">{SCOPE_LABELS[scope] || scope}</span>
                  </div>
                ))}
            </div>
          </div>
        )}
      </div>

      {/* Session Info */}
      <div className="rounded-xl border border-border bg-card/50 p-4 space-y-2">
        <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Session</h4>
        <div className="grid grid-cols-2 gap-3 text-xs">
          <div>
            <span className="text-muted-foreground">Auth Provider</span>
            <p className="font-medium">Keycloak (OAuth 2.1 + PKCE)</p>
          </div>
          <div>
            <span className="text-muted-foreground">Token Status</span>
            <p className="font-medium flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-emerald-400" /> Active
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
