#!/bin/sh
set -eu

# Default matches Docker Compose service name "backend" on port 8000.
# Override for Railway private networking, e.g. my-api.railway.internal:8000
: "${BACKEND_UPSTREAM:=backend:8000}"
export BACKEND_UPSTREAM

# Only substitute BACKEND_UPSTREAM so nginx variables ($host, $uri, …) stay intact.
envsubst '$BACKEND_UPSTREAM' < /etc/nginx/templates/default.conf.template \
  > /etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'
