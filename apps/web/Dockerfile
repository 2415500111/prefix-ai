# syntax=docker/dockerfile:1
# Build context: repository root (the pnpm workspace lockfile lives there).
# Development image: runs `next dev` with hot reload against bind-mounted source.
FROM node:24-alpine

ENV PNPM_HOME=/pnpm \
    PATH="/pnpm:${PATH}" \
    NEXT_TELEMETRY_DISABLED=1 \
    COREPACK_HOME=/corepack \
    COREPACK_ENABLE_DOWNLOAD_PROMPT=0

RUN corepack enable

WORKDIR /app

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
COPY packages/shared/package.json packages/shared/package.json
RUN --mount=type=cache,id=pnpm,target=/pnpm/store \
    pnpm install --frozen-lockfile

COPY packages/shared packages/shared
COPY apps/web apps/web

# .next must exist (owned by node) before Compose mounts a volume over it.
RUN mkdir -p apps/web/.next && chown -R node:node /app /corepack
USER node

WORKDIR /app/apps/web
EXPOSE 3000

HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
  CMD ["node", "-e", "fetch('http://127.0.0.1:3000/api/health').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"]

# Run next directly: `pnpm dev` would first try to re-install into bind-mounted folders.
CMD ["./node_modules/.bin/next", "dev", "--hostname", "0.0.0.0", "--port", "3000"]
