# syntax=docker/dockerfile:1
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm install --legacy-peer-deps

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Next standalone expects /app/public; COPY fails if the repo has no public/ dir
RUN mkdir -p public
ENV NEXT_TELEMETRY_DISABLED=1
# Baked at build time for client bundles (override via compose build.args)
ARG NEXT_PUBLIC_MCP_SERVER_URL=http://localhost:10004
ARG NEXT_PUBLIC_KEYCLOAK_URL=http://localhost:10003
ARG NEXT_PUBLIC_KEYCLOAK_REALM=finint
ARG NEXT_PUBLIC_KEYCLOAK_CLIENT_ID=finint-dashboard
ENV NEXT_PUBLIC_MCP_SERVER_URL=$NEXT_PUBLIC_MCP_SERVER_URL
ENV NEXT_PUBLIC_KEYCLOAK_URL=$NEXT_PUBLIC_KEYCLOAK_URL
ENV NEXT_PUBLIC_KEYCLOAK_REALM=$NEXT_PUBLIC_KEYCLOAK_REALM
ENV NEXT_PUBLIC_KEYCLOAK_CLIENT_ID=$NEXT_PUBLIC_KEYCLOAK_CLIENT_ID
RUN --mount=type=cache,target=/app/.next/cache \
    npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 10005
ENV PORT=10005
ENV HOSTNAME=0.0.0.0

CMD ["node", "server.js"]
