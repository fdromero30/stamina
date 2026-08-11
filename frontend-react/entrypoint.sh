#!/bin/sh
set -e

if [ "${RENDER:-}" = "true" ]; then
  TEMPLATE=/etc/nginx/templates/nginx.render.conf
else
  TEMPLATE=/etc/nginx/templates/nginx.local.conf
fi

USERS_CONFIG_API_URL_HOST=$(echo "${USERS_CONFIG_API_URL}" | sed -E 's|https?://([^/]+)/?.*|\1|')
TRADING_CORE_API_URL_HOST=$(echo "${TRADING_CORE_API_URL}" | sed -E 's|https?://([^/]+)/?.*|\1|')

envsubst \
  '${PORT} ${USERS_CONFIG_API_URL} ${TRADING_CORE_API_URL} ${USERS_CONFIG_API_URL_HOST} ${TRADING_CORE_API_URL_HOST}' \
  < "$TEMPLATE" > /etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'