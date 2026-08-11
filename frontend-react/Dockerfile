FROM node:22-alpine AS build

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
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
