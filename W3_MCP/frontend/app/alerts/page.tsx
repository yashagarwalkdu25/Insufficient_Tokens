"use client";

import { useState, useEffect } from "react";
import { useSession, signIn } from "next-auth/react";
import {
  Bell, BellRing, Plus, Trash2, AlertTriangle, Loader2, Lock,
  TrendingUp, TrendingDown, ShieldAlert, Calendar, CheckCheck,
  BarChart3, Newspaper, Filter,
} from "lucide-react";
import { callMCPTool } from "@/lib/mcp-client";
import { MCP_CLIENT, TIER } from "@/lib/constants";
import { cn, tierBadge, TIER_LEVELS, type Tier } from "@/lib/utils";

interface Alert {
  id: number;
  alert_type: string;
  symbol: string;
  direction: string;
  threshold: number;
  is_triggered: boolean;
  trigger_value?: number;
  triggered_at?: string;
  created_at: string;
}

interface Notification {
  id: number;
  alert_id: number;
  title: string;
  message: string;
  is_read: boolean;
  created_at: string;
}

function alertIcon(alert: Alert) {
  if (alert.alert_type === "price") {
    return alert.direction === "above" ? TrendingUp : TrendingDown;
  }
  const map: Record<string, typeof Bell> = {
    portfolio_risk: ShieldAlert,
    sentiment: Newspaper,
    earnings_reminder: Calendar,
  };
  return map[alert.alert_type] || Bell;
}

function alertColor(alert: Alert) {
  if (alert.alert_type === "price") {
    return alert.direction === "above"
      ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/30"
      : "text-red-400 bg-red-500/10 border-red-500/30";
  }
  const map: Record<string, string> = {
    portfolio_risk: "text-amber-400 bg-amber-500/10 border-amber-500/30",
    sentiment: "text-blue-400 bg-blue-500/10 border-blue-500/30",
    earnings_reminder: "text-purple-400 bg-purple-500/10 border-purple-500/30",
  };
  return map[alert.alert_type] || "text-muted-foreground bg-secondary/50 border-border";
}

export default function AlertsPage() {
  const { data: session, status } = useSession();
  const tier = (session?.tier as string) ?? TIER.Free;
  const tierLevel = TIER_LEVELS[tier as Tier] ?? 0;
  const token = session?.accessToken;

  // Create alert form
  const [alertType, setAlertType] = useState("price_above");
  const [alertSymbol, setAlertSymbol] = useState("");
  const [alertThreshold, setAlertThreshold] = useState("");
  const [showCreate, setShowCreate] = useState(false);

  // Data
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [activeTab, setActiveTab] = useState<"alerts" | "notifications">("notifications");

  // Loading
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  // Auth gate
  if (status === "loading") {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (status === "unauthenticated" || !session) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-4">
        <AlertTriangle className="h-12 w-12 text-amber-400" />
        <h2 className="text-xl font-bold">Authentication Required</h2>
        <p className="text-muted-foreground text-center max-w-md">
          Sign in to manage alerts and view notifications.
        </p>
        <button
          onClick={() => signIn()}
          className="px-6 py-3 rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90 transition-colors"
        >
          Sign In to Continue
        </button>
      </div>
    );
  }

  async function loadAlerts() {
    setLoading(true);
    setError("");
    try {
      const result = await callMCPTool("get_my_alerts", {}, token);
      const data = result.data as Record<string, unknown>;
      setAlerts((data.alerts as Alert[]) || []);
    } catch (e: unknown) {
      const msg = (e as Error).message;
      if (msg === MCP_CLIENT.Error.Forbidden) setError("Alerts require at least Free tier.");
      else setError("Failed to load alerts.");
    } finally {
      setLoading(false);
    }
  }

  async function loadNotifications() {
    setLoading(true);
    setError("");
    try {
      const result = await callMCPTool("get_notifications", { limit: 30 }, token);
      const data = result.data as Record<string, unknown>;
      setNotifications((data.notifications as Notification[]) || []);
    } catch (e: unknown) {
      const msg = (e as Error).message;
      if (msg === MCP_CLIENT.Error.Forbidden) setError("Notifications require at least Free tier.");
      else setError("Failed to load notifications.");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateAlert() {
    if (!alertSymbol.trim() || !alertThreshold.trim()) return;
    setCreating(true);
    setError("");
    try {
      let toolName = "create_price_alert";
      const args: Record<string, unknown> = {
        symbol: alertSymbol.toUpperCase(),
        threshold: parseFloat(alertThreshold),
        direction: alertType === "price_above" ? "above" : "below",
      };

      if (alertType === "portfolio_risk") {
        toolName = "create_portfolio_risk_alert";
        args.risk_threshold = parseFloat(alertThreshold);
        delete args.symbol;
        delete args.threshold;
        delete args.direction;
      } else if (alertType === "sentiment") {
        toolName = "create_sentiment_alert";
        args.threshold = parseFloat(alertThreshold);
        delete args.direction;
      } else if (alertType === "earnings_reminder") {
        toolName = "create_earnings_reminder";
        delete args.threshold;
        delete args.direction;
      }

      const result = await callMCPTool(toolName, args, token);
      const raw = result as unknown as Record<string, unknown>;
      if (raw.error) {
        setError(raw.error as string);
        return;
      }
      setAlertSymbol("");
      setAlertThreshold("");
      setShowCreate(false);
      await loadAlerts();
    } catch (e: unknown) {
      const msg = (e as Error).message;
      if (msg === MCP_CLIENT.Error.Forbidden) setError("This alert type requires a higher tier.");
      else setError("Failed to create alert.");
    } finally {
      setCreating(false);
    }
  }

  async function handleDeleteAlert(alertId: number) {
    try {
      await callMCPTool("delete_alert", { alert_id: alertId }, token);
      setAlerts((prev) => prev.filter((a) => a.id !== alertId));
    } catch {
      setError("Failed to delete alert.");
    }
  }

  async function handleMarkAllRead() {
    try {
      const unreadIds = notifications.filter((n) => !n.is_read).map((n) => n.id);
      if (unreadIds.length === 0) return;
      await callMCPTool("mark_notifications_read", { notification_ids: unreadIds }, token);
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
    } catch {
      setError("Failed to mark as read.");
    }
  }

  async function handleCheckTrigger() {
    setLoading(true);
    setError("");
    try {
      const result = await callMCPTool("check_and_trigger_alerts", {}, token);
      const data = result.data as Record<string, unknown>;
      const triggered = (data.alerts_triggered as number) || 0;
      await loadAlerts();
      await loadNotifications();
      if (triggered === 0) {
        setError("All alerts checked — none triggered at this time.");
      }
    } catch (e: unknown) {
      const msg = (e as Error).message;
      if (msg === MCP_CLIENT.Error.Forbidden) setError("Alert checking requires Premium tier.");
      else setError("Failed to check alerts.");
    } finally {
      setLoading(false);
    }
  }

  const unreadCount = notifications.filter((n) => !n.is_read).length;
  const activeAlerts = alerts.filter((a) => !a.is_triggered);
  const triggeredAlerts = alerts.filter((a) => a.is_triggered);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Bell className="h-6 w-6" /> Alerts & Notifications
          </h1>
          <p className="text-muted-foreground text-sm">
            Create price alerts, risk monitors, and earnings reminders
          </p>
        </div>
        <span className={cn("px-2 py-0.5 rounded-full text-xs font-medium border uppercase", tierBadge(tier))}>{tier}</span>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 shrink-0" /> {error}
        </div>
      )}

      {/* Tab switcher */}
      <div className="flex items-center gap-2 border-b border-border pb-0">
        <button
          onClick={() => { setActiveTab("notifications"); loadNotifications(); }}
          className={cn(
            "px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px",
            activeTab === "notifications"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          )}
        >
          <BellRing className="h-4 w-4 inline mr-1.5" />
          Notifications
          {unreadCount > 0 && (
            <span className="ml-1.5 px-1.5 py-0.5 rounded-full bg-red-500 text-white text-xs font-bold">
              {unreadCount}
            </span>
          )}
        </button>
        <button
          onClick={() => { setActiveTab("alerts"); loadAlerts(); }}
          className={cn(
            "px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px",
            activeTab === "alerts"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          )}
        >
          <ShieldAlert className="h-4 w-4 inline mr-1.5" />
          My Alerts ({alerts.length})
        </button>
      </div>

      {/* ═══ NOTIFICATIONS TAB ═══ */}
      {activeTab === "notifications" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <button
              onClick={loadNotifications}
              disabled={loading}
              className="px-3 py-1.5 rounded-md bg-secondary text-xs hover:bg-secondary/80 disabled:opacity-50"
            >
              {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : "Refresh"}
            </button>
            <div className="flex gap-2">
              <button
                onClick={handleCheckTrigger}
                disabled={loading}
                className="px-3 py-1.5 rounded-md bg-amber-600 text-white text-xs font-medium hover:bg-amber-500 disabled:opacity-50"
              >
                Check Triggers
              </button>
              {unreadCount > 0 && (
                <button
                  onClick={handleMarkAllRead}
                  className="px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-medium hover:bg-primary/90 flex items-center gap-1"
                >
                  <CheckCheck className="h-3 w-3" /> Mark All Read
                </button>
              )}
            </div>
          </div>

          {notifications.length === 0 && !loading && (
            <div className="text-center py-12 text-muted-foreground">
              <BellRing className="h-12 w-12 mx-auto mb-3 opacity-30" />
              <p className="font-medium">No notifications yet</p>
              <p className="text-sm">Create alerts and they&apos;ll trigger notifications when conditions are met.</p>
            </div>
          )}

          <div className="space-y-2">
            {notifications.map((n) => (
              <div
                key={n.id}
                className={cn(
                  "rounded-lg border p-4 text-sm transition-all",
                  n.is_read
                    ? "border-border bg-card opacity-60"
                    : "border-primary/30 bg-primary/5"
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <p className={cn("font-medium", !n.is_read && "text-primary")}>{n.title}</p>
                    <p className="text-muted-foreground text-xs mt-1">{n.message}</p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-xs text-muted-foreground">
                      {n.created_at ? new Date(n.created_at).toLocaleString("en-IN", { dateStyle: "short", timeStyle: "short" }) : "—"}
                    </p>
                    {!n.is_read && (
                      <span className="inline-block mt-1 w-2 h-2 rounded-full bg-primary" />
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ═══ ALERTS TAB ═══ */}
      {activeTab === "alerts" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <button
              onClick={loadAlerts}
              disabled={loading}
              className="px-3 py-1.5 rounded-md bg-secondary text-xs hover:bg-secondary/80 disabled:opacity-50"
            >
              {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : "Refresh"}
            </button>
            <button
              onClick={() => setShowCreate(!showCreate)}
              className="px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-medium hover:bg-primary/90 flex items-center gap-1"
            >
              <Plus className="h-3 w-3" /> New Alert
            </button>
          </div>

          {/* Create Alert Form */}
          {showCreate && (
            <div className="rounded-xl border border-primary/30 bg-card p-4 space-y-3">
              <h3 className="font-semibold text-sm flex items-center gap-2">
                <Plus className="h-4 w-4" /> Create Alert
              </h3>
              <div className="flex flex-wrap gap-2">
                <select
                  value={alertType}
                  onChange={(e) => setAlertType(e.target.value)}
                  className="px-3 py-2 rounded-md bg-secondary border border-border text-sm"
                >
                  <option value="price_above">Price Above</option>
                  <option value="price_below">Price Below</option>
                  {tierLevel >= 1 && <option value="portfolio_risk">Portfolio Risk</option>}
                  {tierLevel >= 1 && <option value="sentiment">Sentiment Alert</option>}
                  <option value="earnings_reminder">Earnings Reminder</option>
                </select>

                {alertType !== "portfolio_risk" && (
                  <input
                    placeholder="Symbol (e.g. TCS)"
                    value={alertSymbol}
                    onChange={(e) => setAlertSymbol(e.target.value.toUpperCase())}
                    className="px-3 py-2 rounded-md bg-secondary border border-border text-sm w-32"
                  />
                )}

                {alertType !== "earnings_reminder" && (
                  <input
                    placeholder={
                      alertType === "portfolio_risk" ? "Risk threshold (0-100)"
                      : alertType === "sentiment" ? "Sentiment threshold (-1 to 1)"
                      : "Price (₹)"
                    }
                    type="number"
                    step="any"
                    value={alertThreshold}
                    onChange={(e) => setAlertThreshold(e.target.value)}
                    className="px-3 py-2 rounded-md bg-secondary border border-border text-sm w-36"
                  />
                )}

                <button
                  onClick={handleCreateAlert}
                  disabled={creating}
                  className="px-4 py-2 rounded-md bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-500 disabled:opacity-50"
                >
                  {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : "Create"}
                </button>
              </div>

              <div className="text-xs text-muted-foreground space-y-1">
                {alertType === "price_above" && <p>Triggers when the stock price goes above your target.</p>}
                {alertType === "price_below" && <p>Triggers when the stock price drops below your target.</p>}
                {alertType === "portfolio_risk" && <p>Triggers when your portfolio risk score exceeds the threshold. <span className={cn("font-medium", tierBadge(TIER.Premium))}>Premium+</span></p>}
                {alertType === "sentiment" && <p>Triggers when news sentiment for a stock drops below the threshold. <span className={cn("font-medium", tierBadge(TIER.Premium))}>Premium+</span></p>}
                {alertType === "earnings_reminder" && <p>Reminds you before a company announces quarterly results.</p>}
              </div>
            </div>
          )}

          {/* Active Alerts */}
          {activeAlerts.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Active Alerts ({activeAlerts.length})</h4>
              {activeAlerts.map((a) => {
                const Icon = alertIcon(a);
                const colorClass = alertColor(a);
                return (
                  <div key={a.id} className={cn("rounded-lg border p-3 text-sm flex items-center justify-between", colorClass)}>
                    <div className="flex items-center gap-3">
                      <Icon className="h-4 w-4 shrink-0" />
                      <div>
                        <p className="font-medium">
                          {a.symbol && <span className="font-mono mr-1">{a.symbol}</span>}
                          {a.direction === "above" ? "above" : a.direction === "below" ? "below" : a.alert_type.replace("_", " ")}
                          {a.threshold ? ` ₹${a.threshold.toLocaleString("en-IN")}` : ""}
                        </p>
                        <p className="text-xs opacity-70">
                          Created {a.created_at ? new Date(a.created_at).toLocaleDateString("en-IN") : "—"}
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={() => handleDeleteAlert(a.id)}
                      className="p-1.5 rounded hover:bg-white/10 transition-colors"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                );
              })}
            </div>
          )}

          {/* Triggered Alerts */}
          {triggeredAlerts.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Triggered ({triggeredAlerts.length})</h4>
              {triggeredAlerts.map((a) => {
                const Icon = alertIcon(a);
                return (
                  <div key={a.id} className="rounded-lg border border-border bg-card/50 p-3 text-sm flex items-center justify-between opacity-60">
                    <div className="flex items-center gap-3">
                      <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />
                      <div>
                        <p className="font-medium line-through">
                          {a.symbol && <span className="font-mono mr-1">{a.symbol}</span>}
                          {a.direction === "above" ? "above" : a.direction === "below" ? "below" : a.alert_type.replace("_", " ")}
                          {a.threshold ? ` ₹${a.threshold.toLocaleString("en-IN")}` : ""}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          Triggered {a.triggered_at ? new Date(a.triggered_at).toLocaleString("en-IN") : "—"}
                          {a.trigger_value ? ` at ₹${a.trigger_value.toLocaleString("en-IN")}` : ""}
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={() => handleDeleteAlert(a.id)}
                      className="p-1.5 rounded hover:bg-white/10 transition-colors"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                );
              })}
            </div>
          )}

          {alerts.length === 0 && !loading && (
            <div className="text-center py-12 text-muted-foreground">
              <ShieldAlert className="h-12 w-12 mx-auto mb-3 opacity-30" />
              <p className="font-medium">No alerts configured</p>
              <p className="text-sm">Create your first alert to get notified when conditions are met.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
