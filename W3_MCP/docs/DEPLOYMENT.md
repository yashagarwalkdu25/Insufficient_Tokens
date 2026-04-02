# Deployment Guide

Local Docker first, then cloud (EC2) notes.

This stack runs **five** services (MCP server, Next.js frontend, Keycloak, Redis, PostgreSQL). Use **`docker compose` from the `W3_MCP` directory** on your machine or on a VM.

On EC2, build and push images from your laptop (private GitHub is fine—you already have the code), then on the server use **`docker-compose.ec2.yml`** plus `.env`, `keycloak/`, and `db/`. No `git clone` on EC2.

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

## AWS EC2 (Docker Hub / registry)

Run the full stack on one instance using **pre-built images** for `mcp-server` and `frontend`, plus public images for Keycloak, Redis, and Postgres.

### Fastest path (checklist)

1. **Laptop** — `docker login`, then build and push both images (`linux/amd64`) with the frontend `NEXT_PUBLIC_*` build-args pointing at `http://YOUR_PUBLIC_HOST:10004` and `:10003` (see step 2 below).
2. **`.env` on the laptop** (you will copy this to EC2) — set at least:
   - `DOCKERHUB_USER=your-dockerhub-user` (compose uses `your-dockerhub-user/w3-mcp-server:latest` and `.../w3-frontend:latest`)
   - `W3_PUBLIC_HOST` — EC2 public IP or DNS (same value as `YOUR_PUBLIC_HOST` in the build commands below)
   - `OAUTH_RESOURCE_URL`, `NEXT_PUBLIC_MCP_SERVER_URL`, `NEXT_PUBLIC_KEYCLOAK_URL`, and `NEXTAUTH_URL` using `http://${W3_PUBLIC_HOST}` with ports **10004**, **10003**, and **10005** respectively so the browser and OAuth agree
   - For frontend image builds: after `set -a && . ./.env && set +a`, pass `--build-arg NEXT_PUBLIC_MCP_SERVER_URL=http://${W3_PUBLIC_HOST}:10004` and `--build-arg NEXT_PUBLIC_KEYCLOAK_URL=http://${W3_PUBLIC_HOST}:10003`
3. **Laptop → EC2** — one `rsync` or `scp` of `docker-compose.ec2.yml`, `.env`, `keycloak/`, `db/` (no repo clone).
4. **EC2** — `docker compose -f docker-compose.ec2.yml pull && docker compose -f docker-compose.ec2.yml up -d`.

### 1. Instance sizing

- **4 GB RAM minimum** (Keycloak + Postgres + Next.js is heavy).
- **Amazon Linux 2023** or **Ubuntu 22.04+**.

### 2. Build and push images (on your laptop or CI)

Use **`linux/amd64`** so images run on typical EC2 instance types.

Replace `YOUR_DOCKERHUB_USER` and set `YOUR_PUBLIC_HOST` to the EC2 public IP or DNS name the **browser** will use.

```bash
cd W3_MCP

# MCP server
docker buildx build --platform linux/amd64 -f mcp-server/Dockerfile \
  -t YOUR_DOCKERHUB_USER/w3-mcp-server:latest ./mcp-server --push

# Frontend — bake public URLs at build time
docker buildx build --platform linux/amd64 -f frontend/Dockerfile \
  --build-arg NEXT_PUBLIC_MCP_SERVER_URL=http://YOUR_PUBLIC_HOST:10004 \
  --build-arg NEXT_PUBLIC_KEYCLOAK_URL=http://YOUR_PUBLIC_HOST:10003 \
  --build-arg NEXT_PUBLIC_KEYCLOAK_REALM=finint \
  --build-arg NEXT_PUBLIC_KEYCLOAK_CLIENT_ID=finint-dashboard \
  -t YOUR_DOCKERHUB_USER/w3-frontend:latest ./frontend --push
```

If `buildx` is unavailable: `docker build --platform linux/amd64 ...`, then `docker login` and `docker push` each tag.

**Shortcut:** from `W3_MCP/`, after `docker login` and with `DOCKERHUB_USER` and `W3_PUBLIC_HOST` set in `.env`, run `./deploy-image.sh` (optional: `IMAGE_TAG=v1 PLATFORM=linux/amd64` — `docker-compose.ec2.yml` expects `:latest` unless you change image tags there).

### 3. Install Docker on EC2 (Amazon Linux 2023 example)

```bash
sudo yum update -y
sudo yum install -y docker
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ec2-user
# Log out and back in so `docker` works without sudo
```

Install the Compose plugin if needed:

```bash
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
```

### 4. Copy files to EC2 (no `git clone`)

Use **`docker-compose.ec2.yml`** in the repo: it pulls `mcp-server` and `frontend` from your registry and does not use `build:`.

From the machine that has your private repo checked out (repo root = `Insufficient_Tokens/`):

```bash
# From repo root; set USER@HOST (e.g. ec2-user@1.2.3.4)
export EC2=ec2-user@YOUR_EC2_IP

rsync -avz W3_MCP/docker-compose.ec2.yml W3_MCP/.env "$EC2:~/w3-mcp/"
rsync -avz W3_MCP/keycloak/ "$EC2:~/w3-mcp/keycloak/"
rsync -avz W3_MCP/db/ "$EC2:~/w3-mcp/db/"
```

Equivalent with `scp`:

```bash
scp W3_MCP/docker-compose.ec2.yml W3_MCP/.env ec2-user@YOUR_EC2_IP:~/w3-mcp/
scp -r W3_MCP/keycloak W3_MCP/db ec2-user@YOUR_EC2_IP:~/w3-mcp/
```

On the instance:

```bash
cd ~/w3-mcp
docker compose -f docker-compose.ec2.yml pull
docker compose -f docker-compose.ec2.yml up -d
```

After `.env` changes: `docker compose -f docker-compose.ec2.yml up -d` (add `--force-recreate` if services ignore new env). After new images: `pull` then `up -d` again.

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
cd ~/w3-mcp
docker compose -f docker-compose.ec2.yml logs -f
docker compose -f docker-compose.ec2.yml pull
docker compose -f docker-compose.ec2.yml up -d
```

---

## Troubleshooting

| Issue | What to check |
|-------|----------------|
| Keycloak never healthy | `docker compose logs keycloak` — first import can take 60s+ |
| Frontend cannot reach MCP | `NEXT_PUBLIC_MCP_SERVER_URL` must match what the **browser** uses (not `http://mcp-server:10004`) |
| 401 / OAuth errors | `OAUTH_RESOURCE_URL` and Keycloak realm client settings vs public URL |
| Out of memory | Increase EC2 instance size or stop unused services |

For development commands and API smoke tests, see the **Quick Start** and **Development** sections in the repository [README.md](../README.md).
