# syntax=docker/dockerfile:1
FROM node:24-bookworm-slim AS dependencies
WORKDIR /app
RUN npm install --global pnpm@11.25.0
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

FROM dependencies AS build
COPY index.html vite.config.js ./
COPY src ./src
COPY public ./public
# Keep browser requests on the same origin as the page.
ENV VITE_API_BASE_URL=/api/v1
ARG VITE_OPPORTUNITY_SOURCE_URLS=true
ENV VITE_OPPORTUNITY_SOURCE_URLS=${VITE_OPPORTUNITY_SOURCE_URLS}
RUN pnpm build

FROM nginx:1.30.5-alpine AS runtime
ENV API_PROXY_TARGET=http://host.docker.internal:8000
ENV NGINX_ENVSUBST_FILTER=^API_PROXY_TARGET$
COPY docker/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1/healthz || exit 1
