import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export function formatCurrency(
  value: number,
  currency: string = "INR",
  compact: boolean = false,
): string {
  if (compact) {
    if (Math.abs(value) >= 1e7) {
      return `₹${(value / 1e7).toFixed(2)} Cr`;
    }
    if (Math.abs(value) >= 1e5) {
      return `₹${(value / 1e5).toFixed(2)} L`;
    }
  }
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

export function formatPercent(value: number): string {
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

export function formatNumber(value: number, decimals: number = 2): string {
  return new Intl.NumberFormat("en-IN", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

export function formatCompactNumber(value: number): string {
  if (Math.abs(value) >= 1e7) return `${(value / 1e7).toFixed(1)} Cr`;
  if (Math.abs(value) >= 1e5) return `${(value / 1e5).toFixed(1)} L`;
  if (Math.abs(value) >= 1e3) return `${(value / 1e3).toFixed(1)} K`;
  return value.toFixed(0);
}

export function timeAgo(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return date.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

export type Tier = "free" | "premium" | "analyst" | "admin";

export const TIER_CONFIG: Record<
  Tier,
  { label: string; color: string; rateLimit: number }
> = {
  free: { label: "Free", color: "tier-free", rateLimit: 30 },
  premium: { label: "Premium", color: "tier-premium", rateLimit: 150 },
  analyst: { label: "Analyst", color: "tier-analyst", rateLimit: 500 },
  admin: { label: "Admin", color: "tier-admin", rateLimit: 9999 },
};

export function getTierFromRoles(roles: string[]): Tier {
  if (roles.includes("admin")) return "admin";
  if (roles.includes("analyst")) return "analyst";
  if (roles.includes("premium")) return "premium";
  return "free";
}
