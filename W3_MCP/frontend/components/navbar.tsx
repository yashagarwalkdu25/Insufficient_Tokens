"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession, signIn, signOut } from "next-auth/react";
import { KEYCLOAK_ROLE, TIER } from "@/lib/constants";
import { cn, tierBadge } from "@/lib/utils";
import {
  Search,
  Briefcase,
  BarChart3,
  Settings,
  LogIn,
  LogOut,
  Shield,
  User,
  UserPlus,
} from "lucide-react";

const tabs = [
  { href: "/research", label: "Research Copilot", icon: Search, id: "ps1" },
  { href: "/portfolio", label: "Portfolio Monitor", icon: Briefcase, id: "ps2" },
  { href: "/earnings", label: "Earnings Center", icon: BarChart3, id: "ps3" },
  { href: "/settings", label: "Settings", icon: Settings, id: "settings" },
];

export function Navbar() {
  const pathname = usePathname();
  const { data: session } = useSession();
  const tier = session?.user?.tier ?? session?.tier ?? TIER.Free;
  const roles: string[] = session?.user?.roles ?? [];
  const isAdmin = roles.includes(KEYCLOAK_ROLE.Admin);

  return (
    <nav className="border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-50">
      <div className="container mx-auto max-w-7xl px-4">
        <div className="flex h-14 items-center justify-between">
          <div className="flex items-center gap-6">
            <Link href="/" className="flex items-center gap-2 font-bold text-lg">
              <Shield className="h-5 w-5 text-primary" />
              <span>FinInt</span>
            </Link>

            <div className="hidden md:flex items-center gap-1">
              {tabs.map((tab) => {
                const Icon = tab.icon;
                const active = pathname === tab.href;
                return (
                  <Link
                    key={tab.id}
                    href={tab.href}
                    className={cn(
                      "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors",
                      active
                        ? "bg-primary/10 text-primary"
                        : "text-muted-foreground hover:text-foreground hover:bg-muted"
                    )}
                  >
                    <Icon className="h-4 w-4" />
                    {tab.label}
                  </Link>
                );
              })}
              {isAdmin && (
                <Link
                  href="/admin"
                  className={cn(
                    "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors",
                    pathname === "/admin"
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted"
                  )}
                >
                  <Shield className="h-4 w-4" />
                  Admin
                </Link>
              )}
            </div>
          </div>

          <div className="flex items-center gap-3">
            {session ? (
              <>
                <span
                  className={cn(
                    "px-2 py-0.5 rounded-full text-xs font-medium border uppercase tracking-wide",
                    tierBadge(tier)
                  )}
                >
                  {tier}
                </span>
                <Link
                  href="/profile"
                  className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  <User className="h-4 w-4" />
                  <span className="hidden sm:inline">{session.user?.name || session.user?.email}</span>
                </Link>
                <button
                  onClick={() => signOut()}
                  className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  <LogOut className="h-4 w-4" />
                </button>
              </>
            ) : (
              <>
                <Link
                  href="/signup"
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  <UserPlus className="h-4 w-4" />
                  Sign Up
                </Link>
                <button
                  onClick={() => signIn("keycloak", undefined, { prompt: "login" })}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
                >
                  <LogIn className="h-4 w-4" />
                  Sign In
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}
