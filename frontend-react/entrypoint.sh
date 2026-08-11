#!/bin/sh
set -e

if [ "${RENDER:-}" = "true" ]; then
  TEMPLATE=/etc/nginx/templates/nginx.render.conf
else
  TEMPLATE=/etc/nginx/templates/nginx.local.conf
fi

envsubst '${PORT} ${USERS_CONFIG_API_URL} ${TRADING_CORE_API_URL}' < "$TEMPLATE" > /etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'