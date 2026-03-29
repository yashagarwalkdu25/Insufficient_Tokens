import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

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
    case "analyst": return "text-purple-400";
    case "premium": return "text-amber-400";
    default: return "text-emerald-400";
  }
}

export function tierBadge(tier: string): string {
  switch (tier) {
    case "admin": return "bg-red-500/20 text-red-300 border-red-500/30";
    case "analyst": return "bg-purple-500/20 text-purple-300 border-purple-500/30";
    case "premium": return "bg-amber-500/20 text-amber-300 border-amber-500/30";
    default: return "bg-emerald-500/20 text-emerald-300 border-emerald-500/30";
  }
}

export type Tier = "free" | "premium" | "analyst" | "admin";

export const TIER_CONFIG: Record<
  Tier,
  { label: string; color: string; rateLimit: number }
> = {
  free: { label: "Free", color: "tier-free", rateLimit: 30 },
  premium: { label: "Premium", color: "tier-premium", rateLimit: 100 },
  analyst: { label: "Analyst", color: "tier-analyst", rateLimit: 300 },
  admin: { label: "Admin", color: "tier-admin", rateLimit: 9999 },
};
