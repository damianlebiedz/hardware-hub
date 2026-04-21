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
# Serve the compiled assets with nginx.  The nginx.conf proxies /api requests
# to the FastAPI backend container on the Docker Compose internal network.
FROM nginx:1.27-alpine AS runtime

# Remove the default nginx config and replace with ours.
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy compiled assets from the builder stage.
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
