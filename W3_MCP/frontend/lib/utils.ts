import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { TIER, type Tier } from "./constants";

export type { Tier } from "./constants";
export { TIER } from "./constants";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(value: number | null | undefined): string {
  if (value == null) return "—";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(value);
}

export function formatPercent(value: number | null | undefined): string {
  if (value == null) return "—";
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

export function tierColor(tier: string): string {
  switch (tier) {
    case TIER.Analyst: return "text-purple-400";
    case TIER.Premium: return "text-amber-400";
    default: return "text-emerald-400";
  }
}

export function tierBadge(tier: string): string {
  switch (tier) {
    case TIER.Admin: return "bg-red-500/20 text-red-300 border-red-500/30";
    case TIER.Analyst: return "bg-purple-500/20 text-purple-300 border-purple-500/30";
    case TIER.Premium: return "bg-amber-500/20 text-amber-300 border-amber-500/30";
    default: return "bg-emerald-500/20 text-emerald-300 border-emerald-500/30";
  }
}

/** Numeric rank for gating premium (≥1) and analyst (≥2) UI. Admin matches analyst access. */
export const TIER_LEVELS: Record<Tier, number> = {
  [TIER.Free]: 0,
  [TIER.Premium]: 1,
  [TIER.Analyst]: 2,
  [TIER.Admin]: 2,
};

export const TIER_CONFIG: Record<
  Tier,
  { label: string; color: string; rateLimit: number }
> = {
  [TIER.Free]: { label: "Free", color: "tier-free", rateLimit: 30 },
  [TIER.Premium]: { label: "Premium", color: "tier-premium", rateLimit: 100 },
  [TIER.Analyst]: { label: "Analyst", color: "tier-analyst", rateLimit: 300 },
  [TIER.Admin]: { label: "Admin", color: "tier-admin", rateLimit: 9999 },
};
