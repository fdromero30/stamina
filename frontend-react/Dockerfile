FROM node:22-alpine AS build

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
# Build args para inyectar URLs de API en el bundle JS:
# - Local: /api y /trading-core (relativas → Nginx proxy)
# - Render: https://users-config-backend.onrender.com (absolutas → CORS directo)
ARG VITE_USERS_CONFIG_API_URL=/api
ARG VITE_TRADING_CORE_URL=/trading-core
ENV VITE_USERS_CONFIG_API_URL=$VITE_USERS_CONFIG_API_URL
ENV VITE_TRADING_CORE_URL=$VITE_TRADING_CORE_URL
RUN npm run build

FROM nginx:1.27-alpine
RUN apk add --no-cache gettext
COPY --from=build /app/dist /usr/share/nginx/html
# Templates por entorno: Render usa HTTPS+SNI, local usa red interna HTTP
COPY nginx.local.conf /etc/nginx/templates/nginx.local.conf
COPY nginx.render.conf /etc/nginx/templates/nginx.render.conf
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
EXPOSE 80
ENV USERS_CONFIG_API_URL=http://users-config-backend:8080
ENV TRADING_CORE_API_URL=http://trading-core:8000
ENV PORT=80
ENTRYPOINT ["/entrypoint.sh"]