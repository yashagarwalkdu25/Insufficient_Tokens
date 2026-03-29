import type { NextAuthOptions } from "next-auth";
import type { JWT } from "next-auth/jwt";

const KEYCLOAK_PUBLIC_URL =
  process.env.NEXT_PUBLIC_KEYCLOAK_URL || "http://localhost:10003";
const KEYCLOAK_INTERNAL_URL =
  process.env.KEYCLOAK_ISSUER || KEYCLOAK_PUBLIC_URL;
const KEYCLOAK_REALM =
  process.env.NEXT_PUBLIC_KEYCLOAK_REALM || "finint";
const KEYCLOAK_CLIENT_ID =
  process.env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID || "finint-dashboard";

// Browser-facing URLs (user's browser hits localhost:10003)
const PUBLIC_REALM = `${KEYCLOAK_PUBLIC_URL}/realms/${KEYCLOAK_REALM}`;
// Server-side URLs (Docker container hits keycloak:8080)
const INTERNAL_REALM = `${KEYCLOAK_INTERNAL_URL}/realms/${KEYCLOAK_REALM}`;

export const authOptions: NextAuthOptions = {
  providers: [
    {
      id: "keycloak",
      name: "Keycloak",
      type: "oauth",
      clientId: KEYCLOAK_CLIENT_ID,
      clientSecret: "",
      checks: ["pkce", "state"],
      // Browser redirect → public URL
      authorization: {
        url: `${PUBLIC_REALM}/protocol/openid-connect/auth`,
        params: { scope: "openid profile email", prompt: "login" },
      },
      // Server-side endpoints → internal Docker URL
      token: {
        url: `${INTERNAL_REALM}/protocol/openid-connect/token`,
        params: { client_id: KEYCLOAK_CLIENT_ID },
      },
      userinfo: `${INTERNAL_REALM}/protocol/openid-connect/userinfo`,
      client: { token_endpoint_auth_method: "none" },
      issuer: PUBLIC_REALM,
      idToken: true,
      profile(profile) {
        return {
          id: profile.sub,
          name: profile.name || profile.preferred_username,
          email: profile.email,
          image: null,
        };
      },
    },
  ],
  session: {
    strategy: "jwt",
    maxAge: 60 * 60, // 1 hour
  },
  debug: true,
  callbacks: {
    async jwt({ token, account, user, profile }) {
      console.log("[AUTH] jwt callback", {
        hasAccount: !!account,
        hasUser: !!user,
        hasProfile: !!profile,
        accountType: account?.type,
        accountProvider: account?.provider,
        hasAccessToken: !!account?.access_token,
        hasIdToken: !!account?.id_token,
        userName: user?.name,
        userEmail: user?.email,
      });

      if (account) {
        token.accessToken = account.access_token;
        token.refreshToken = account.refresh_token;
        token.expiresAt = account.expires_at;
        token.idToken = account.id_token;

        // Decode access token to extract realm_access.roles AND user info
        try {
          const payload = JSON.parse(
            Buffer.from((account.access_token as string).split(".")[1], "base64").toString()
          );
          token.roles = payload.realm_access?.roles || [];
          token.name = payload.name || payload.preferred_username || token.name;
          token.email = payload.email || token.email;
          console.log("[AUTH] decoded AT", {
            roles: token.roles,
            name: token.name,
            email: token.email,
          });
        } catch (err) {
          console.error("[AUTH] failed to decode AT", err);
          token.roles = [];
        }
        token.tier = getTierFromRoles(token.roles as string[]);

        // Also pick up from the user object (returned by profile() callback)
        if (user) {
          token.name = token.name || user.name;
          token.email = token.email || user.email;
        }
      }

      // Also pick up from profile if available
      if (profile) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const p = profile as any;
        token.name = token.name || p.name || p.preferred_username;
        token.email = token.email || p.email;
      }

      // Check if token needs refresh
      if (token.expiresAt && Date.now() < (token.expiresAt as number) * 1000) {
        return token;
      }

      return refreshAccessToken(token);
    },
    async session({ session, token }) {
      console.log("[AUTH] session callback", {
        tokenName: token.name,
        tokenEmail: token.email,
        tokenRoles: token.roles,
        tokenTier: token.tier,
        tokenSub: token.sub,
      });
      return {
        ...session,
        accessToken: token.accessToken,
        user: {
          ...session.user,
          id: token.sub || "",
          name: token.name || session.user?.name || null,
          email: token.email || session.user?.email || null,
          roles: (token.roles as string[]) || [],
          tier: (token.tier as string) || "free",
          scopes: getScopesForTier((token.tier as string) || "free"),
        },
      };
    },
  },
  pages: {
    error: "/",
  },
};

function getTierFromRoles(roles: string[]): string {
  if (roles.includes("admin")) return "admin";
  if (roles.includes("analyst")) return "analyst";
  if (roles.includes("premium")) return "premium";
  return "free";
}

function getScopesForTier(tier: string): string[] {
  const base = ["market:read", "mf:read", "news:read", "watchlist:read", "watchlist:write"];
  if (tier === "free") return base;

  const premium = [
    ...base,
    "fundamentals:read",
    "technicals:read",
    "macro:read",
    "portfolio:read",
    "portfolio:write",
    "filings:read",
  ];
  if (tier === "premium") return premium;

  const analyst = [
    ...premium,
    "filings:deep",
    "macro:historical",
    "research:generate",
  ];
  return analyst; // analyst and admin both get all scopes
}

async function refreshAccessToken(token: JWT): Promise<JWT> {
  try {
    const url = `${INTERNAL_REALM}/protocol/openid-connect/token`;
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        client_id: KEYCLOAK_CLIENT_ID,
        grant_type: "refresh_token",
        refresh_token: token.refreshToken as string,
      }),
    });

    const data = await response.json();

    if (!response.ok) throw data;

    return {
      ...token,
      accessToken: data.access_token,
      refreshToken: data.refresh_token ?? token.refreshToken,
      expiresAt: Math.floor(Date.now() / 1000) + data.expires_in,
    };
  } catch {
    return { ...token, error: "RefreshAccessTokenError" };
  }
}
