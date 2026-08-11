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

# Defaults hardcodeados para los upstreams del proxy Nginx.
# Sin estos, si Render no tiene las variables en el dashboard, Nginx usa
# los defaults del Dockerfile (http://users-config-backend:8080) que son
# hostnames de Docker Compose y NO existen en Render → 502.
#
# IMPORTANTE: En RENDER forzamos SIEMPRE las URLs correctas, sin importar
# lo que tenga el dashboard de Render (puede tener valores viejos que ya
# no existen → 502). Si el nombre del servicio cambia, se actualiza aquí.
if [ "${RENDER:-}" = "true" ] || [ "${PORT:-80}" != "80" ]; then
  USERS_CONFIG_API_URL="https://users-config-backend.onrender.com"
  TRADING_CORE_API_URL="https://trading-core-qthd.onrender.com"
else
  if [ -z "${USERS_CONFIG_API_URL:-}" ]; then
    USERS_CONFIG_API_URL="https://users-config-backend.onrender.com"
  fi
  if [ -z "${TRADING_CORE_API_URL:-}" ]; then
    TRADING_CORE_API_URL="https://trading-core-qthd.onrender.com"
  fi
fi
export USERS_CONFIG_API_URL TRADING_CORE_API_URL

# Generate Nginx config (proxy upstreams — internal hostnames)
envsubst '${PORT} ${USERS_CONFIG_API_URL} ${TRADING_CORE_API_URL}' < "$TEMPLATE" > /etc/nginx/conf.d/default.conf

# Generate runtime config.js for the BROWSER:
#   - Both local and Render: relative paths (/api, /trading-core) → Nginx proxies
# The VITE_* vars are only used for LOCAL override to a remote backend.
BROWSER_USERS_URL="${VITE_USERS_CONFIG_API_URL:-}"
BROWSER_TRADING_URL="${VITE_TRADING_CORE_URL:-}"

if [ "${RENDER:-}" = "true" ] || [ "${PORT:-80}" != "80" ]; then
  # On Render:
  #  - usersConfigApiUrl: URL absoluta directa al backend Java. CORS ya está
  #    habilitado en el backend para https://stamina-frontend.onrender.com,
  #    así que la autenticación funciona igual que antes (sin depender de proxy).
  #  - tradingCoreUrl: ruta relativa → Nginx proxya a TRADING_CORE_API_URL
  #    (hardcodeada con el default correcto arriba). Así el health de Python
  #    siempre apunta a la URL actual sin depender de VITE_* viejos.
  BROWSER_USERS_URL="${VITE_USERS_CONFIG_API_URL:-https://users-config-backend.onrender.com}"
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