"use client";

import { useState } from "react";
import { signIn } from "next-auth/react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { UserPlus, Loader2, CheckCircle2, AlertTriangle, Shield } from "lucide-react";


export default function SignUpPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    username: "",
    email: "",
    firstName: "",
    lastName: "",
    password: "",
    confirmPassword: "",
  });
  const [status, setStatus] = useState<"idle" | "submitting" | "success" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");

  function updateField(field: string, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErrorMsg("");

    if (!form.username || !form.email) {
      setErrorMsg("Username and email are required.");
      return;
    }
    if (form.username.length < 3) {
      setErrorMsg("Username must be at least 3 characters.");
      return;
    }
    if (form.password.length < 6) {
      setErrorMsg("Password must be at least 6 characters.");
      return;
    }
    if (form.password !== form.confirmPassword) {
      setErrorMsg("Passwords do not match.");
      return;
    }

    setStatus("submitting");

    try {
      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: form.username,
          email: form.email,
          firstName: form.firstName,
          lastName: form.lastName,
          password: form.password,
        }),
      });

      const data = await res.json();

      if (res.status === 409) {
        setErrorMsg("Username or email already exists.");
        setStatus("error");
        return;
      }

      if (!res.ok) {
        setErrorMsg(data.error || "Failed to create account.");
        setStatus("error");
        return;
      }

      setStatus("success");

      // Auto sign-in after 1.5s — force login prompt so user enters new credentials
      setTimeout(() => {
        signIn("keycloak", undefined, { prompt: "login" });
      }, 1500);
    } catch {
      setErrorMsg("Failed to connect to server.");
      setStatus("error");
    }
  }

  return (
    <div className="flex items-center justify-center min-h-[70vh]">
      <div className="w-full max-w-md space-y-6">
        <div className="text-center space-y-2">
          <div className="flex items-center justify-center gap-2">
            <Shield className="h-8 w-8 text-primary" />
            <h1 className="text-2xl font-bold">Create Account</h1>
          </div>
          <p className="text-muted-foreground text-sm">
            Sign up for a free FinInt account. New accounts start on the <span className="text-emerald-400 font-medium">Free</span> tier.
          </p>
        </div>

        {status === "success" ? (
          <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-6 text-center space-y-3">
            <CheckCircle2 className="h-10 w-10 text-emerald-400 mx-auto" />
            <h3 className="font-semibold text-lg">Account Created!</h3>
            <p className="text-sm text-muted-foreground">Signing you in automatically...</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="rounded-xl border border-border bg-card p-6 space-y-4">
            {errorMsg && (
              <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 shrink-0" /> {errorMsg}
              </div>
            )}

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className="text-xs text-muted-foreground font-medium">First Name</label>
                <input
                  type="text"
                  value={form.firstName}
                  onChange={(e) => updateField("firstName", e.target.value)}
                  placeholder="John"
                  className="w-full px-3 py-2 rounded-md bg-secondary border border-border text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs text-muted-foreground font-medium">Last Name</label>
                <input
                  type="text"
                  value={form.lastName}
                  onChange={(e) => updateField("lastName", e.target.value)}
                  placeholder="Doe"
                  className="w-full px-3 py-2 rounded-md bg-secondary border border-border text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs text-muted-foreground font-medium">Username *</label>
              <input
                type="text"
                value={form.username}
                onChange={(e) => updateField("username", e.target.value)}
                placeholder="johndoe"
                required
                className="w-full px-3 py-2 rounded-md bg-secondary border border-border text-sm focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs text-muted-foreground font-medium">Email *</label>
              <input
                type="email"
                value={form.email}
                onChange={(e) => updateField("email", e.target.value)}
                placeholder="john@example.com"
                required
                className="w-full px-3 py-2 rounded-md bg-secondary border border-border text-sm focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs text-muted-foreground font-medium">Password *</label>
              <input
                type="password"
                value={form.password}
                onChange={(e) => updateField("password", e.target.value)}
                placeholder="Min 6 characters"
                required
                className="w-full px-3 py-2 rounded-md bg-secondary border border-border text-sm focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs text-muted-foreground font-medium">Confirm Password *</label>
              <input
                type="password"
                value={form.confirmPassword}
                onChange={(e) => updateField("confirmPassword", e.target.value)}
                placeholder="Repeat password"
                required
                className="w-full px-3 py-2 rounded-md bg-secondary border border-border text-sm focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>

            <button
              type="submit"
              disabled={status === "submitting"}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              {status === "submitting" ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <UserPlus className="h-4 w-4" />
              )}
              {status === "submitting" ? "Creating Account..." : "Create Account"}
            </button>

            <p className="text-center text-xs text-muted-foreground">
              Already have an account?{" "}
              <button
                type="button"
                onClick={() => signIn("keycloak", undefined, { prompt: "login" })}
                className="text-primary hover:underline"
              >
                Sign In
              </button>
            </p>
          </form>
        )}

        <div className="rounded-lg border border-border bg-card/50 p-4 space-y-2">
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Tier Info</h4>
          <div className="grid grid-cols-3 gap-2 text-xs">
            <div className="rounded-md bg-emerald-500/10 border border-emerald-500/20 p-2 text-center">
              <p className="font-medium text-emerald-300">Free</p>
              <p className="text-muted-foreground">14 tools</p>
            </div>
            <div className="rounded-md bg-amber-500/10 border border-amber-500/20 p-2 text-center">
              <p className="font-medium text-amber-300">Premium</p>
              <p className="text-muted-foreground">30 tools</p>
            </div>
            <div className="rounded-md bg-purple-500/10 border border-purple-500/20 p-2 text-center">
              <p className="font-medium text-purple-300">Analyst</p>
              <p className="text-muted-foreground">44 tools</p>
            </div>
          </div>
          <p className="text-[11px] text-muted-foreground/60">Upgrade requests can be submitted from Settings. Admin approval required.</p>
        </div>
      </div>
    </div>
  );
}
