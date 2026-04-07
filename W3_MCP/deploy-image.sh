#!/usr/bin/env bash
# Build linux/amd64 images and push to Docker Hub. Reads W3_MCP/.env for:
#   DOCKERHUB_USER, W3_PUBLIC_HOST
# Optional: NEXT_PUBLIC_KEYCLOAK_REALM, NEXT_PUBLIC_KEYCLOAK_CLIENT_ID (defaults match .env.example)
# Optional env overrides: ENV_FILE, PLATFORM, IMAGE_TAG
# Prereq: docker login

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

ENV_FILE="${ENV_FILE:-$ROOT/.env}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE (copy from .env.example)" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

: "${DOCKERHUB_USER:?Set DOCKERHUB_USER in $ENV_FILE}"
: "${W3_PUBLIC_HOST:?Set W3_PUBLIC_HOST in $ENV_FILE (EC2 public IP or DNS)}"

PLATFORM="${PLATFORM:-linux/amd64}"
TAG="${IMAGE_TAG:-latest}"
REALM="${NEXT_PUBLIC_KEYCLOAK_REALM:-finint}"
CLIENT_ID="${NEXT_PUBLIC_KEYCLOAK_CLIENT_ID:-finint-dashboard}"

MCP_IMG="${DOCKERHUB_USER}/w3-mcp-server:${TAG}"
FE_IMG="${DOCKERHUB_USER}/w3-frontend:${TAG}"
MCP_URL="http://${W3_PUBLIC_HOST}:10004"
KC_URL="http://${W3_PUBLIC_HOST}:10003"

echo "Pushing to Docker Hub as ${DOCKERHUB_USER} (platform=${PLATFORM}, tag=${TAG})"
echo "  ${MCP_IMG}"
echo "  ${FE_IMG}"
echo "  Frontend build-args: NEXT_PUBLIC_MCP_SERVER_URL=${MCP_URL} NEXT_PUBLIC_KEYCLOAK_URL=${KC_URL}"

docker buildx build --platform "$PLATFORM" -f mcp-server/Dockerfile \
  -t "$MCP_IMG" ./mcp-server --push

docker buildx build --platform "$PLATFORM" -f frontend/Dockerfile \
  --build-arg "NEXT_PUBLIC_MCP_SERVER_URL=${MCP_URL}" \
  --build-arg "NEXT_PUBLIC_KEYCLOAK_URL=${KC_URL}" \
  --build-arg "NEXT_PUBLIC_KEYCLOAK_REALM=${REALM}" \
  --build-arg "NEXT_PUBLIC_KEYCLOAK_CLIENT_ID=${CLIENT_ID}" \
  -t "$FE_IMG" ./frontend --push

echo "Done."
