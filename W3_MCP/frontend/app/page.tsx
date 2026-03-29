"use client";

import { useSession, signIn } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Shield, Search, Briefcase, BarChart3, Lock } from "lucide-react";
import { cn, tierBadge } from "@/lib/utils";

const tiers = [
  {
    name: "Free",
    tools: 14,
    rate: "30 calls/hr",
    features: [
      "Stock quotes & price history",
      "Mutual fund NAV lookup",
      "Company & market news",
      "Portfolio add/remove & health check",
      "Earnings calendar & results dates",
    ],
    color: "border-emerald-500/30",
    user: "free_user / free123",
  },
  {
    name: "Premium",
    tools: 30,
    rate: "150 calls/hr",
    features: [
      "All Free features",
      "Fundamental ratios & financials",
      "Technical indicators (RSI, SMA, MACD)",
      "Shareholding patterns & news sentiment",
      "MF overlap & macro sensitivity",
      "EPS history, pre-earnings profiles",
      "Option chain, post-results reaction",
      "Macro data (RBI rates, CPI, GDP)",
    ],
    color: "border-blue-500/30",
    user: "premium_user / premium123",
  },
  {
    name: "Analyst",
    tools: 44,
    rate: "500 calls/hr",
    features: [
      "All Premium features",
      "Cross-source signal analysis",
      "AI research brief generation",
      "Portfolio risk reports & what-if",
      "Cross-source earnings verdicts",
      "Earnings season dashboard",
      "Cross-company comparison",
      "Filing document access & AI parsing",
    ],
    color: "border-amber-500/30",
    user: "analyst_user / analyst123",
  },
];

const useCases = [
  { icon: Search, title: "PS1: Research Copilot", desc: "Full-stack research assistant — 'tell me everything about Reliance'", href: "/research" },
  { icon: Briefcase, title: "PS2: Portfolio Monitor", desc: "Portfolio watchdog with risk detection and cross-source alerts", href: "/portfolio" },
  { icon: BarChart3, title: "PS3: Earnings Center", desc: "Earnings analysis with filing parsing and market reaction", href: "/earnings" },
];

export default function LandingPage() {
  const { data: session } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (session) router.push("/research");
  }, [session, router]);

  return (
    <div className="space-y-12 py-8">
      <section className="text-center space-y-4">
        <div className="flex items-center justify-center gap-3">
          <Shield className="h-10 w-10 text-primary" />
          <h1 className="text-4xl font-bold tracking-tight">Indian Financial Intelligence</h1>
        </div>
        <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
          MCP-powered unified intelligence layer wrapping 7+ Indian financial data
          sources with OAuth 2.1 tiered access, cross-source reasoning, and AI agent analysis.
        </p>
        <button
          onClick={() => signIn("keycloak", undefined, { prompt: "login" })}
          className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-primary text-primary-foreground font-medium text-lg hover:bg-primary/90 transition-colors"
        >
          <Lock className="h-5 w-5" />
          Sign in with Keycloak
        </button>
      </section>

      <section className="space-y-4">
        <h2 className="text-2xl font-semibold text-center">Three Use Cases, One Server</h2>
        <div className="grid md:grid-cols-3 gap-4">
          {useCases.map((uc) => {
            const Icon = uc.icon;
            return (
              <div key={uc.title} className="rounded-xl border border-border bg-card p-6 space-y-3">
                <Icon className="h-8 w-8 text-primary" />
                <h3 className="font-semibold text-lg">{uc.title}</h3>
                <p className="text-sm text-muted-foreground">{uc.desc}</p>
              </div>
            );
          })}
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="text-2xl font-semibold text-center">Tiered Access</h2>
        <div className="grid md:grid-cols-3 gap-4">
          {tiers.map((t) => (
            <div key={t.name} className={cn("rounded-xl border bg-card p-6 space-y-3", t.color)}>
              <span className={cn("px-2 py-0.5 rounded-full text-xs font-medium border uppercase", tierBadge(t.name.toLowerCase()))}>
                {t.name}
              </span>
              <div className="flex gap-3 text-xs text-muted-foreground">
                <span><span className="font-medium text-foreground">{t.tools}</span> tools</span>
                <span><span className="font-medium text-foreground">{t.rate}</span></span>
              </div>
              <ul className="space-y-1.5 text-sm text-muted-foreground">
                {t.features.map((f) => (
                  <li key={f} className="flex items-start gap-2">
                    <span className="text-primary mt-0.5">•</span>
                    {f}
                  </li>
                ))}
              </ul>
              <p className="text-xs text-muted-foreground/60 font-mono">Demo: {t.user}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
