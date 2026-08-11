#!/bin/sh
set -e

# Detect environment
if [ "${RENDER:-}" = "true" ] || [ "${PORT:-80}" != "80" ]; then
  echo "[entrypoint] Render environment detected"
  TEMPLATE=/etc/nginx/templates/nginx.render.conf
else
  echo "[entrypoint] Local environment detected"
  TEMPLATE=/etc/nginx/templates/nginx.local.conf
fi

# Generate Nginx config (proxy upstreams — internal hostnames)
envsubst '${PORT} ${USERS_CONFIG_API_URL} ${TRADING_CORE_API_URL}' < "$TEMPLATE" > /etc/nginx/conf.d/default.conf

# Generate runtime config.js for the BROWSER:
#   - Local (PORT=80): relative paths (/api, /trading-core) → Nginx proxies
#   - Render (PORT!=80): absolute URLs → browser calls backends directly (CORS)
# The VITE_* vars are set in docker-compose.yml for local, and in render.yaml
# via dockerBuildArgs for Render.
BROWSER_USERS_URL="${VITE_USERS_CONFIG_API_URL:-}"
BROWSER_TRADING_URL="${VITE_TRADING_CORE_URL:-}"

if [ "${RENDER:-}" = "true" ] || [ "${PORT:-80}" != "80" ]; then
  # On Render, the browser must use the public HTTPS URLs
  BROWSER_USERS_URL="${VITE_USERS_CONFIG_API_URL:-${USERS_CONFIG_API_URL}}"
  BROWSER_TRADING_URL="${VITE_TRADING_CORE_URL:-${TRADING_CORE_API_URL}}"
else
  # On local, the browser uses relative paths proxied by Nginx
  [ -z "$BROWSER_USERS_URL" ] && BROWSER_USERS_URL="/api"
  [ -z "$BROWSER_TRADING_URL" ] && BROWSER_TRADING_URL="/trading-core"
fi

cat > /usr/share/nginx/html/config.js <<EOF
window.__STAMINA_CONFIG__ = {
  usersConfigApiUrl: "${BROWSER_USERS_URL}",
  tradingCoreUrl: "${BROWSER_TRADING_URL}"
};
EOF

echo "[entrypoint] Browser config.js:"
cat /usr/share/nginx/html/config.js

exec nginx -g 'daemon off;'