import { MCP_CLIENT } from "./constants";

const MCP_SERVER_URL = process.env.NEXT_PUBLIC_MCP_SERVER_URL || "http://localhost:10004";

export interface MCPToolResult {
  data: Record<string, unknown>;
  source: string;
  cache_status: string;
  timestamp: string;
  disclaimer: string;
}

export async function callMCPTool(
  toolName: string,
  args: Record<string, unknown>,
  accessToken?: string
): Promise<MCPToolResult> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  const res = await fetch(`${MCP_SERVER_URL}/api/tool/${toolName}`, {
    method: "POST",
    headers,
    body: JSON.stringify(args),
  });

  if (res.status === 401) throw new Error(MCP_CLIENT.Error.Unauthorized);
  if (res.status === 403) throw new Error(MCP_CLIENT.Error.Forbidden);
  if (res.status === 429) {
    const retryAfter = res.headers.get("Retry-After") || "60";
    throw new Error(`${MCP_CLIENT.Prefix.RateLimited}${retryAfter}`);
  }
  if (!res.ok) throw new Error(`${MCP_CLIENT.Prefix.Http}${res.status}`);

  return res.json();
}

export async function fetchMCPResource(
  uri: string,
  accessToken?: string
): Promise<unknown> {
  const headers: Record<string, string> = {};
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  const res = await fetch(
    `${MCP_SERVER_URL}/api/resource?uri=${encodeURIComponent(uri)}`,
    { headers }
  );
  if (!res.ok) throw new Error(`${MCP_CLIENT.Prefix.Resource}${res.status}`);
  return res.json();
}

export async function getServerStatus(): Promise<Record<string, unknown>> {
  const res = await fetch(`${MCP_SERVER_URL}/api/status`);
  if (!res.ok) throw new Error(MCP_CLIENT.Error.Status);
  return res.json();
}

export async function getHealthCheck(): Promise<{ status: string }> {
  const res = await fetch(`${MCP_SERVER_URL}/health`);
  if (!res.ok) throw new Error(MCP_CLIENT.Error.Health);
  const j = (await res.json()) as { status?: string };
  const raw = j.status ?? "unknown";
  return { status: raw === "healthy" ? "ok" : raw };
}
