import type { NextAuthOptions } from "next-auth";
import type { JWT } from "next-auth/jwt";
import { KEYCLOAK_ROLE, TIER, type Tier } from "./constants";

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
      authorization: {
        url: `${PUBLIC_REALM}/protocol/openid-connect/auth`,
        params: { scope: "openid profile email", prompt: "login" },
      },
      token: {
        url: `${INTERNAL_REALM}/protocol/openid-connect/token`,
        params: { client_id: KEYCLOAK_CLIENT_ID },
      },
      userinfo: `${INTERNAL_REALM}/protocol/openid-connect/userinfo`,
      client: { token_endpoint_auth_method: "none" },
      jwks_endpoint: `${INTERNAL_REALM}/protocol/openid-connect/certs`,
      issuer: PUBLIC_REALM,
      idToken: true,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      profile(profile: any) {
        return {
          id: profile.sub,
          name: profile.name || profile.preferred_username,
          email: profile.email,
          image: null,
        };
      },
    },
  ],
  session: { strategy: "jwt", maxAge: 60 * 60 },
  callbacks: {
    async jwt({ token, account, user, profile }) {
      if (account) {
        token.accessToken = account.access_token;
        token.refreshToken = account.refresh_token;
        token.expiresAt = account.expires_at;
        token.idToken = account.id_token;

        // Decode access token to extract realm_access.roles + user claims
        try {
          const payload = JSON.parse(
            Buffer.from((account.access_token as string).split(".")[1], "base64").toString()
          );
          token.roles = payload.realm_access?.roles || [];
          token.name = payload.name || payload.preferred_username || token.name;
          token.email = payload.email || token.email;
        } catch {
          token.roles = [];
        }
        token.tier = getTierFromRoles(token.roles as string[]);

        // Fallback: pick up from user object (returned by profile() callback)
        if (user) {
          token.name = token.name || user.name;
          token.email = token.email || user.email;
        }
      }

      if (profile) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const p = profile as any;
        token.name = token.name || p.name || p.preferred_username;
        token.email = token.email || p.email;
      }

      // Token refresh check
      if (token.expiresAt && Date.now() < (token.expiresAt as number) * 1000) {
        return token;
      }

      return refreshAccessToken(token);
    },
    async session({ session, token }) {
      const tier = (token.tier as string) || TIER.Free;
      return {
        ...session,
        accessToken: token.accessToken,
        tier,
        user: {
          ...session.user,
          id: token.sub || "",
          name: token.name || session.user?.name || null,
          email: token.email || session.user?.email || null,
          roles: (token.roles as string[]) || [],
          tier,
          scopes: getScopesForTier(tier),
        },
      };
    },
  },
  pages: {
    error: "/",
  },
};

function getTierFromRoles(roles: string[]): Tier {
  if (roles.includes(KEYCLOAK_ROLE.Admin)) return TIER.Admin;
  if (roles.includes(KEYCLOAK_ROLE.Analyst)) return TIER.Analyst;
  if (roles.includes(KEYCLOAK_ROLE.Premium)) return TIER.Premium;
  return TIER.Free;
}

function getScopesForTier(tier: string): string[] {
  const base = ["market:read", "mf:read", "news:read", "watchlist:read", "watchlist:write"];
  if (tier === TIER.Free) return base;

  const premium = [
    ...base,
    "fundamentals:read",
    "technicals:read",
    "macro:read",
    "portfolio:read",
    "portfolio:write",
    "filings:read",
  ];
  if (tier === TIER.Premium) return premium;

  return [
    ...premium,
    "filings:deep",
    "macro:historical",
    "research:generate",
  ];
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
