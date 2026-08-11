#!/bin/sh
set -e

# Detect environment:
#   - Render: inyecta PORT != 80 (ej: 10000) y opcionalmente RENDER=true
#   - Local:  Docker Compose usa PORT=80
if [ "${RENDER:-}" = "true" ] || [ "${PORT:-80}" != "80" ]; then
  echo "[entrypoint] Render environment detected"
  TEMPLATE=/etc/nginx/templates/nginx.render.conf
else
  echo "[entrypoint] Local environment detected"
  TEMPLATE=/etc/nginx/templates/nginx.local.conf
fi

envsubst '${PORT} ${USERS_CONFIG_API_URL} ${TRADING_CORE_API_URL}' < "$TEMPLATE" > /etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'