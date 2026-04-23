#!/bin/sh
set -eu

# Default matches Docker Compose service name "backend" on port 8000.
# Override for Railway private networking, e.g. my-api.railway.internal:8000
: "${BACKEND_UPSTREAM:=backend:8000}"
export BACKEND_UPSTREAM

# Railway routes public traffic to $PORT; locally it is unset — use 80 (docker-compose maps 5173:80).
: "${PORT:=80}"
export PORT

# DNS for nginx "resolver" (needed for variable proxy_pass). Railway often lists an IPv6 nameserver
# first; nginx requires IPv6 resolver addresses in brackets or it treats "::" as a port delimiter.
DNS_SERVER=$(awk '/^nameserver[[:space:]]+/ { print $2; exit }' /etc/resolv.conf || true)
: "${DNS_SERVER:=127.0.0.11}"
case "$DNS_SERVER" in *:*)
  DNS_SERVER="[${DNS_SERVER}]"
  ;;
esac
export DNS_SERVER

# Only substitute these vars so nginx variables ($host, $uri, …) stay intact.
envsubst '$BACKEND_UPSTREAM $PORT $DNS_SERVER' < /etc/nginx/templates/default.conf.template \
  > /etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'
