#!/bin/sh
set -eu

# Single variable BACKEND_UPSTREAM:
#   Docker Compose (default):  backend:8000
#   Railway private DNS:         my-service.railway.internal:8000
#   Railway public URL:          https://my-backend-xxxx.up.railway.app
: "${BACKEND_UPSTREAM:=backend:8000}"
export BACKEND_UPSTREAM

: "${PORT:=80}"
export PORT

# Public HTTPS base URL → nginx.public.conf.template
case "$BACKEND_UPSTREAM" in
  http://*|https://*)
    BACKEND_UPSTREAM="${BACKEND_UPSTREAM%/}"
    export BACKEND_UPSTREAM
    envsubst '$PORT $BACKEND_UPSTREAM' < /etc/nginx/templates/nginx.public.conf.template \
      > /etc/nginx/conf.d/default.conf
    ;;
  *)
    DNS_SERVER=$(awk '/^nameserver[[:space:]]+/ { print $2; exit }' /etc/resolv.conf || true)
    : "${DNS_SERVER:=127.0.0.11}"
    case "$DNS_SERVER" in *:*)
      DNS_SERVER="[${DNS_SERVER}]"
      ;;
    esac
    export DNS_SERVER
    envsubst '$BACKEND_UPSTREAM $PORT $DNS_SERVER' < /etc/nginx/templates/default.conf.template \
      > /etc/nginx/conf.d/default.conf
    ;;
esac

exec nginx -g 'daemon off;'
