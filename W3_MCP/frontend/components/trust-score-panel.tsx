"use client";

import { AlertTriangle, CheckCircle2, HelpCircle, Shield } from "lucide-react";
import { cn } from "@/lib/utils";

export interface TrustConflict {
  topic?: string;
  status?: string;
  sources?: string[];
  details?: string;
}

export interface TrustSignalSummary {
  confirmations?: number;
  contradictions?: number;
  missing?: number;
}

/** Renders MCP cross-source trust metadata when present on tool `data`. */
export function TrustScorePanel({
  payload,
  className,
}: {
  payload: Record<string, unknown> | null | undefined;
  className?: string;
}) {
  if (!payload || payload.trust_score == null) return null;
  const score = Math.round(Number(payload.trust_score));
  if (Number.isNaN(score)) return null;

  const summary = payload.signal_summary as TrustSignalSummary | undefined;
  const confirmations = summary?.confirmations ?? 0;
  const contradictions = summary?.contradictions ?? 0;
  const missing = summary?.missing ?? 0;
  const conflicts = (payload.conflicts as TrustConflict[]) || [];
  const reasoning = (payload.trust_score_reasoning as string[]) || [];

  const scoreColor =
    score >= 70 ? "text-emerald-400" : score >= 45 ? "text-amber-400" : "text-red-400";

  return (
    <div
      className={cn(
        "rounded-lg border border-purple-500/25 bg-purple-500/5 p-4 space-y-3 text-sm",
        className
      )}
    >
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <p className="font-semibold text-purple-200 flex items-center gap-2">
          <Shield className="h-4 w-4 shrink-0 text-purple-400" />
          Trust score
        </p>
        <p className={cn("text-2xl font-bold tabular-nums", scoreColor)}>
          {score}
          <span className="text-sm font-normal text-muted-foreground"> / 100</span>
        </p>
      </div>

      <div className="grid grid-cols-3 gap-2 text-xs">
        <div className="flex items-center gap-1.5 rounded-md bg-secondary/60 px-2 py-1.5">
          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
          <span className="text-muted-foreground">Confirmed</span>
          <span className="ml-auto font-mono font-medium">{confirmations}</span>
        </div>
        <div className="flex items-center gap-1.5 rounded-md bg-secondary/60 px-2 py-1.5">
          <AlertTriangle className="h-3.5 w-3.5 text-amber-400 shrink-0" />
          <span className="text-muted-foreground">Conflict</span>
          <span className="ml-auto font-mono font-medium">{contradictions}</span>
        </div>
        <div className="flex items-center gap-1.5 rounded-md bg-secondary/60 px-2 py-1.5">
          <HelpCircle className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          <span className="text-muted-foreground">Missing</span>
          <span className="ml-auto font-mono font-medium">{missing}</span>
        </div>
      </div>

      {conflicts.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-amber-200/90">Structured conflicts</p>
          <ul className="space-y-1 text-xs text-muted-foreground">
            {conflicts.map((c, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-amber-500/80 shrink-0">•</span>
                <span>{c.details || c.topic || "Conflict"}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {reasoning.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs font-medium text-muted-foreground">Reasoning</p>
          <ul className="text-xs text-muted-foreground/90 space-y-0.5">
            {reasoning.slice(0, 8).map((line, i) => (
              <li key={i} className="pl-2 border-l border-border/60">
                {line}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
