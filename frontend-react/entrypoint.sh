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
#   - Both local and Render: relative paths (/api, /trading-core) → Nginx proxies
# The VITE_* vars are only used for LOCAL override to a remote backend.
BROWSER_USERS_URL="${VITE_USERS_CONFIG_API_URL:-}"
BROWSER_TRADING_URL="${VITE_TRADING_CORE_URL:-}"

if [ "${RENDER:-}" = "true" ] || [ "${PORT:-80}" != "80" ]; then
  # On Render: Nginx proxya /api y /trading-core hacia los backends.
  # Usamos SIEMPRE rutas relativas para no depender de URLs absolutas
  # que puedan quedar desactualizadas en el dashboard de Render.
  BROWSER_USERS_URL="/api"
  BROWSER_TRADING_URL="/trading-core"
else
  # On local: default to relative paths proxied by Nginx,
  # BUT allow override to a production backend via VITE_* absolute URLs:
  #   VITE_USERS_CONFIG_API_URL=https://users-config-backend.onrender.com
  #   VITE_TRADING_CORE_URL=https://trading-core-qthd.onrender.com
  case "$BROWSER_USERS_URL" in
    http://*|https://*) ;;                      # absolute URL → use as-is
    *) BROWSER_USERS_URL="/api" ;;              # otherwise proxy via Nginx
  esac
  case "$BROWSER_TRADING_URL" in
    http://*|https://*) ;;                      # absolute URL → use as-is
    *) BROWSER_TRADING_URL="/trading-core" ;;   # otherwise proxy via Nginx
  esac
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