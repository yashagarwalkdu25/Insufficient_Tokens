/**
 * Single source of truth for earnings command-center tool panels (toggle + MCP mapping).
 */

import { TIER } from "./constants";

export const EARNINGS_PANEL_KEYS = [
  "eps",
  "pre",
  "expect",
  "options",
  "reaction",
  "avse",
  "verdict",
  "dashboard",
  "compare",
] as const;

export type EarningsPanelKey = (typeof EARNINGS_PANEL_KEYS)[number];

export type EarningsFetchContext = {
  symbolUpper: string;
  compareSymbols: string;
};

export type EarningsPanelVariant = typeof TIER.Premium | typeof TIER.Analyst;

export type EarningsPanelFetchSpec = {
  tool: string;
  label: string;
  variant: EarningsPanelVariant;
  needsSymbol: boolean;
  /** Require non-empty compareSymbols before fetch (quarterly compare only). */
  needsCompareSymbols: boolean;
  buildBody: (ctx: EarningsFetchContext) => Record<string, unknown>;
  forbiddenMsg: string;
  loadFailedMsg: string;
};

export const EARNINGS_PANEL_FETCH = {
  eps: {
    tool: "get_eps_history",
    label: "EPS History",
    variant: TIER.Premium,
    needsSymbol: true,
    needsCompareSymbols: false,
    buildBody: ({ symbolUpper }) => ({ symbol: symbolUpper, quarters: 8 }),
    forbiddenMsg: "EPS History requires Premium tier.",
    loadFailedMsg: "Failed to load EPS history.",
  },
  pre: {
    tool: "get_pre_earnings_profile",
    label: "Pre-Earnings Profile",
    variant: TIER.Premium,
    needsSymbol: true,
    needsCompareSymbols: false,
    buildBody: ({ symbolUpper }) => ({ symbol: symbolUpper }),
    forbiddenMsg: "Pre-earnings profile requires Premium tier.",
    loadFailedMsg: "Failed to load pre-earnings profile.",
  },
  expect: {
    tool: "get_analyst_expectations",
    label: "Analyst Expectations",
    variant: TIER.Premium,
    needsSymbol: true,
    needsCompareSymbols: false,
    buildBody: ({ symbolUpper }) => ({ symbol: symbolUpper }),
    forbiddenMsg: "Analyst expectations requires Premium tier.",
    loadFailedMsg: "Failed to load expectations.",
  },
  options: {
    tool: "get_option_chain",
    label: "Option Chain",
    variant: TIER.Premium,
    needsSymbol: true,
    needsCompareSymbols: false,
    buildBody: ({ symbolUpper }) => ({ symbol: symbolUpper }),
    forbiddenMsg: "Option chain requires Premium tier.",
    loadFailedMsg: "Failed to load option chain.",
  },
  reaction: {
    tool: "get_post_results_reaction",
    label: "Post-Results Reaction",
    variant: TIER.Premium,
    needsSymbol: true,
    needsCompareSymbols: false,
    buildBody: ({ symbolUpper }) => ({ symbol: symbolUpper }),
    forbiddenMsg: "Post-results reaction requires Premium tier.",
    loadFailedMsg: "Failed to load post-results reaction.",
  },
  avse: {
    tool: "compare_actual_vs_expected",
    label: "Beat / Miss Analysis",
    variant: TIER.Premium,
    needsSymbol: true,
    needsCompareSymbols: false,
    buildBody: ({ symbolUpper }) => ({ symbol: symbolUpper }),
    forbiddenMsg: "Beat/miss analysis requires Premium tier.",
    loadFailedMsg: "Failed to compare actual vs expected.",
  },
  verdict: {
    tool: "earnings_verdict",
    label: "Run Earnings Verdict",
    variant: TIER.Analyst,
    needsSymbol: true,
    needsCompareSymbols: false,
    buildBody: ({ symbolUpper }) => ({ symbol: symbolUpper }),
    forbiddenMsg: "Earnings verdict requires Analyst tier.",
    loadFailedMsg: "Failed to run earnings verdict.",
  },
  dashboard: {
    tool: "earnings_season_dashboard",
    label: "Season Dashboard",
    variant: TIER.Analyst,
    needsSymbol: false,
    needsCompareSymbols: false,
    buildBody: () => ({}),
    forbiddenMsg: "Season dashboard requires Analyst tier.",
    loadFailedMsg: "Failed to load dashboard.",
  },
  compare: {
    tool: "compare_quarterly_performance",
    label: "Compare",
    variant: TIER.Analyst,
    needsSymbol: false,
    needsCompareSymbols: true,
    buildBody: ({ compareSymbols }) => ({ symbols: compareSymbols }),
    forbiddenMsg: "Quarterly comparison requires Analyst tier.",
    loadFailedMsg: "Failed to compare.",
  },
} satisfies Record<EarningsPanelKey, EarningsPanelFetchSpec>;

export function isEarningsPanelKey(s: string): s is EarningsPanelKey {
  return (EARNINGS_PANEL_KEYS as readonly string[]).includes(s);
}

export function earningsPanelIsPremium(key: EarningsPanelKey): boolean {
  return EARNINGS_PANEL_FETCH[key].variant === TIER.Premium;
}
