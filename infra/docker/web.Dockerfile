FROM node:22-slim
WORKDIR /app
ARG NEXT_PUBLIC_API_BASE_URL=/api
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
ENV npm_config_registry=https://registry.npmmirror.com
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/web/package.json ./apps/web/package.json
RUN corepack enable && pnpm install --frozen-lockfile
COPY apps/web ./apps/web
RUN pnpm --dir apps/web build
RUN chown -R 10001:10001 /app
USER 10001
CMD ["node", "apps/web/node_modules/next/dist/bin/next", "start", "apps/web"]
