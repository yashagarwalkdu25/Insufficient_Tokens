# Deployment Guide

Local Docker first, then cloud (EC2) notes.

This stack runs **five** services (MCP server, Next.js frontend, Keycloak, Redis, PostgreSQL). Use **`docker compose` from the `W3_MCP` directory** on your machine or on a VM.

---

## Local Docker (recommended)

Work from the folder that contains `docker-compose.yml` (repository path: `W3_MCP/`).

```bash
cd W3_MCP
cp .env.example .env
# Edit .env — OPENAI_API_KEY is required; other keys improve data quality

docker compose up -d --build
```

Wait until all services are healthy (first start can take 1–2 minutes while Keycloak imports the realm).

### Access

| URL | Service |
|-----|---------|
| http://localhost:10005 | Next.js dashboard |
| http://localhost:10004 | MCP server (REST bridge + `POST /mcp`) |
| http://localhost:10003 | Keycloak (admin console: `admin` / `admin` from compose) |

### Verify

```bash
curl -s http://localhost:10004/health | python3 -m json.tool
curl -s http://localhost:10004/.well-known/oauth-protected-resource | python3 -m json.tool
docker compose ps
```

### Logs and lifecycle

```bash
docker compose logs -f mcp-server
docker compose restart mcp-server
docker compose down
# Clear Redis cache (optional)
docker compose exec redis redis-cli FLUSHDB
```

---

## AWS EC2 (Docker Compose on a single instance)

Use this when you want a remote demo of the full stack without publishing multiple images separately.

### 1. Instance sizing

- **4 GB RAM minimum** (Keycloak + Postgres + Next.js build/runtime is heavy).
- **Amazon Linux 2023** or **Ubuntu 22.04+**.

### 2. Install Docker (Amazon Linux 2023 example)

```bash
sudo yum update -y
sudo yum install -y docker git
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ec2-user
# Log out and back in so `docker` works without sudo
```

Install the Compose plugin (if not bundled):

```bash
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
```

### 3. Clone and configure

```bash
git clone <your-repo-url>
cd Insufficient_Tokens/W3_MCP   # adjust if your clone path differs
cp .env.example .env
nano .env   # set OPENAI_API_KEY and optional data API keys
```

### 4. Public URLs and frontend build args

The frontend image is built with `NEXT_PUBLIC_*` URLs. For a public IP or DNS name, set **build arguments** before build so the browser calls the right MCP and Keycloak endpoints.

Edit `docker-compose.yml` **or** export overrides, then build:

```bash
# Example: replace YOUR_EC2_PUBLIC_IP
export NEXT_PUBLIC_HOST=YOUR_EC2_PUBLIC_IP
docker compose build --build-arg NEXT_PUBLIC_MCP_SERVER_URL=http://${NEXT_PUBLIC_HOST}:10004 \
  --build-arg NEXT_PUBLIC_KEYCLOAK_URL=http://${NEXT_PUBLIC_HOST}:10003 \
  frontend
docker compose up -d
```

Alternatively, change the `args:` under `frontend.build` in `docker-compose.yml` to your public host, then `docker compose up -d --build`.

Set `OAUTH_RESOURCE_URL` in `.env` to the **browser-reachable** MCP base URL (e.g. `http://YOUR_EC2_PUBLIC_IP:10004`) so OAuth protected-resource metadata matches where clients connect.

### 5. Security group (AWS console)

| Port | Purpose | Notes |
|------|---------|--------|
| **22** | SSH | Restrict to your IP |
| **10005** | Dashboard | Often `0.0.0.0/0` for demos |
| **10004** | MCP / REST bridge | If external MCP clients connect |
| **10003** | Keycloak | Prefer restricting in production; required if browser OIDC hits this host |

**Do not** expose **10001** (Postgres) or **10002** (Redis) to the public internet in production. The default compose maps them for local debugging; tighten the security group for cloud.

### 6. Management

```bash
cd ~/Insufficient_Tokens/W3_MCP   # your path
docker compose logs -f
docker compose pull   # only if using pre-pushed images
docker compose up -d --build
```

---

## Optional: pushing images to Docker Hub

You can build and push **each** service image (`mcp-server`, `frontend`, plus use public images for Keycloak/Redis/Postgres), then point `docker-compose.yml` at `image:` instead of `build:`. That is optional and heavier to operate than **compose on EC2** with a single clone + build on the instance.

---

## Troubleshooting

| Issue | What to check |
|-------|----------------|
| Keycloak never healthy | `docker compose logs keycloak` — first import can take 60s+ |
| Frontend cannot reach MCP | `NEXT_PUBLIC_MCP_SERVER_URL` must match what the **browser** uses (not `http://mcp-server:10004`) |
| 401 / OAuth errors | `OAUTH_RESOURCE_URL` and Keycloak realm client settings vs public URL |
| Out of memory | Increase EC2 instance size or stop unused services |

For development commands and API smoke tests, see the **Quick Start** and **Development** sections in the repository [README.md](../README.md).
