# ── Stage 1: builder ──────────────────────────────────────────────────────────
# Install dependencies and compile the Vite/Vue application into static assets.
FROM node:22-alpine AS builder

WORKDIR /app

# Copy manifests first for layer-caching — a rebuild is only triggered when
# package.json or package-lock.json actually changes.
COPY package.json package-lock.json* ./
RUN npm ci

# Copy source and build
COPY . .
RUN npm run build

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
# Runtime nginx: BACKEND_UPSTREAM is either host:port (Compose) or https://… (Railway public URL).
FROM nginx:1.27-alpine AS runtime

RUN apk add --no-cache gettext

RUN rm -f /etc/nginx/conf.d/default.conf

COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY nginx.public.conf.template /etc/nginx/templates/nginx.public.conf.template
COPY docker-entrypoint.sh /docker-entrypoint.sh
# Strip Windows CRLF so the shebang stays valid (avoids: exec: no such file)
RUN sed -i 's/\r$//' /docker-entrypoint.sh && chmod +x /docker-entrypoint.sh

ENV BACKEND_UPSTREAM=backend:8000

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
ENTRYPOINT ["/docker-entrypoint.sh"]
