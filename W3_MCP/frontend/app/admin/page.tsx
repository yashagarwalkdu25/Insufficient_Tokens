"use client";

import { useState, useEffect, useCallback } from "react";
import { useSession } from "next-auth/react";
import { Shield, Check, X, RefreshCcw, AlertTriangle, Loader2 } from "lucide-react";
import { cn, tierBadge } from "@/lib/utils";

interface TierRequest {
  id: string;
  user_id: string;
  username: string;
  email: string;
  current_tier: string;
  requested_tier: string;
  status: "pending" | "approved" | "rejected";
  created_at: string;
  reviewed_at?: string;
}

const API = process.env.NEXT_PUBLIC_MCP_SERVER_URL || "http://localhost:10004";

export default function AdminPage() {
  const { data: session } = useSession();
  const token = session?.accessToken;

  const [requests, setRequests] = useState<TierRequest[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const fetchRequests = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API}/api/admin/tier-requests`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.status === 403) { setError("Admin access required."); return; }
      if (!res.ok) { setError("Failed to load requests."); return; }
      const data = await res.json();
      setRequests(data.requests || []);
    } catch {
      setError("Failed to connect to server.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (token) fetchRequests();
  }, [token, fetchRequests]);

  async function handleAction(reqId: string, action: "approve" | "reject") {
    setActionLoading(reqId);
    try {
      const res = await fetch(`${API}/api/admin/tier-requests/${reqId}/${action}`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) {
        setRequests((prev) =>
          prev.map((r) =>
            r.id === reqId ? { ...r, status: action === "approve" ? "approved" : "rejected", reviewed_at: new Date().toISOString() } : r
          )
        );
      }
    } catch {
      setError("Action failed.");
    } finally {
      setActionLoading(null);
    }
  }

  const pending = requests.filter((r) => r.status === "pending");
  const processed = requests.filter((r) => r.status !== "pending");

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2"><Shield className="h-6 w-6" /> Admin Panel</h1>
          <p className="text-muted-foreground">Manage tier upgrade requests</p>
        </div>
        <button onClick={fetchRequests} disabled={loading} className="flex items-center gap-1 px-3 py-1.5 rounded-md bg-secondary text-sm hover:bg-secondary/80 disabled:opacity-50">
          <RefreshCcw className={cn("h-4 w-4", loading && "animate-spin")} /> Refresh
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive flex items-center gap-2">
          <AlertTriangle className="h-4 w-4" /> {error}
        </div>
      )}

      {/* Pending Requests */}
      <div className="rounded-xl border border-border bg-card p-4 space-y-3">
        <h3 className="font-semibold">Pending Requests ({pending.length})</h3>
        {pending.length === 0 ? (
          <p className="text-sm text-muted-foreground">No pending requests.</p>
        ) : (
          <div className="space-y-2">
            {pending.map((req) => (
              <div key={req.id} className="flex items-center justify-between p-4 rounded-lg bg-secondary/50 border border-border">
                <div className="space-y-1">
                  <p className="font-medium text-sm">{req.username || req.user_id} <span className="text-muted-foreground text-xs">({req.email})</span></p>
                  <div className="flex items-center gap-2 text-xs">
                    <span className={cn("px-1.5 py-0.5 rounded border uppercase", tierBadge(req.current_tier))}>{req.current_tier}</span>
                    <span className="text-muted-foreground">→</span>
                    <span className={cn("px-1.5 py-0.5 rounded border uppercase", tierBadge(req.requested_tier))}>{req.requested_tier}</span>
                  </div>
                  <p className="text-xs text-muted-foreground">{new Date(req.created_at).toLocaleString()}</p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleAction(req.id, "approve")}
                    disabled={actionLoading === req.id}
                    className="flex items-center gap-1 px-3 py-1.5 rounded-md bg-emerald-600 text-white text-xs font-medium hover:bg-emerald-500 disabled:opacity-50"
                  >
                    {actionLoading === req.id ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />} Approve
                  </button>
                  <button
                    onClick={() => handleAction(req.id, "reject")}
                    disabled={actionLoading === req.id}
                    className="flex items-center gap-1 px-3 py-1.5 rounded-md bg-red-600 text-white text-xs font-medium hover:bg-red-500 disabled:opacity-50"
                  >
                    <X className="h-3 w-3" /> Reject
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Processed Requests */}
      {processed.length > 0 && (
        <div className="rounded-xl border border-border bg-card p-4 space-y-3">
          <h3 className="font-semibold">Processed Requests ({processed.length})</h3>
          <div className="space-y-2">
            {processed.map((req) => (
              <div key={req.id} className="flex items-center justify-between p-3 rounded-lg bg-secondary/30 text-sm">
                <div>
                  <span className="font-medium">{req.username || req.user_id}</span>
                  <span className="text-muted-foreground ml-2 text-xs">
                    {req.current_tier} → {req.requested_tier}
                  </span>
                </div>
                <span className={cn(
                  "px-2 py-0.5 rounded-full text-xs font-medium",
                  req.status === "approved" ? "bg-emerald-500/20 text-emerald-300" : "bg-red-500/20 text-red-300"
                )}>
                  {req.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
