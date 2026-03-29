import { NextRequest, NextResponse } from "next/server";

const KEYCLOAK_INTERNAL_URL =
  process.env.KEYCLOAK_ISSUER || "http://keycloak:8080";
const KEYCLOAK_REALM = process.env.NEXT_PUBLIC_KEYCLOAK_REALM || "finint";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { username, email, firstName, lastName, password } = body;

    if (!username || !email || !password) {
      return NextResponse.json(
        { error: "Username, email, and password are required." },
        { status: 400 }
      );
    }
    if (typeof username === "string" && username.length < 3) {
      return NextResponse.json(
        { error: "Username must be at least 3 characters." },
        { status: 400 }
      );
    }
    if (typeof password === "string" && password.length < 6) {
      return NextResponse.json(
        { error: "Password must be at least 6 characters." },
        { status: 400 }
      );
    }

    // Get admin token from Keycloak (server-side, no CORS issues)
    const tokenRes = await fetch(
      `${KEYCLOAK_INTERNAL_URL}/realms/master/protocol/openid-connect/token`,
      {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          grant_type: "password",
          client_id: "admin-cli",
          username: process.env.KEYCLOAK_ADMIN || "admin",
          password: process.env.KEYCLOAK_ADMIN_PASSWORD || "admin",
        }),
      }
    );

    if (!tokenRes.ok) {
      return NextResponse.json(
        { error: "Authentication server unavailable." },
        { status: 503 }
      );
    }

    const { access_token } = await tokenRes.json();

    // Create user in Keycloak
    const createRes = await fetch(
      `${KEYCLOAK_INTERNAL_URL}/admin/realms/${KEYCLOAK_REALM}/users`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${access_token}`,
        },
        body: JSON.stringify({
          username,
          email,
          firstName: firstName || "",
          lastName: lastName || "",
          enabled: true,
          emailVerified: true,
          credentials: [
            {
              type: "password",
              value: password,
              temporary: false,
            },
          ],
        }),
      }
    );

    if (createRes.status === 409) {
      return NextResponse.json(
        { error: "Username or email already exists." },
        { status: 409 }
      );
    }

    if (!createRes.ok) {
      const errData = await createRes.json().catch(() => ({}));
      return NextResponse.json(
        { error: errData.errorMessage || "Failed to create account." },
        { status: createRes.status }
      );
    }

    return NextResponse.json({ success: true });
  } catch {
    return NextResponse.json(
      { error: "Failed to connect to authentication server." },
      { status: 500 }
    );
  }
}
