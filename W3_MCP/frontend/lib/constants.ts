/**
 * Canonical strings for tiers, Keycloak realm roles, and MCP HTTP client errors.
 */

export const TIER = {
  Free: "free",
  Premium: "premium",
  Analyst: "analyst",
  Admin: "admin",
} as const;

export type Tier = (typeof TIER)[keyof typeof TIER];

/** Tiers shown in marketing / comparison tables (admin maps to analyst access in UI). */
export const PUBLIC_TIER_ORDER = [TIER.Free, TIER.Premium, TIER.Analyst] as const;
export type PublicTier = (typeof PUBLIC_TIER_ORDER)[number];

export const KEYCLOAK_ROLE = {
  Admin: "admin",
  Analyst: "analyst",
  Premium: "premium",
} as const;

export const MCP_CLIENT = {
  Error: {
    Unauthorized: "UNAUTHORIZED",
    Forbidden: "FORBIDDEN",
    Status: "STATUS_ERROR",
    Health: "HEALTH_ERROR",
  },
  Prefix: {
    RateLimited: "RATE_LIMITED:",
    Http: "MCP_ERROR:",
    Resource: "RESOURCE_ERROR:",
  },
} as const;
