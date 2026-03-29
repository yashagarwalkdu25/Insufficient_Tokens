import "next-auth";

declare module "next-auth" {
  interface Session {
    accessToken?: string;
    tier?: string;
    user: {
      id: string;
      name?: string | null;
      email?: string | null;
      image?: string | null;
      roles: string[];
      tier: string;
      scopes: string[];
    };
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    accessToken?: string;
    refreshToken?: string;
    idToken?: string;
    expiresAt?: number;
    roles?: string[];
    tier?: string;
    error?: string;
  }
}
