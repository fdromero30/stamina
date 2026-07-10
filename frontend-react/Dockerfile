FROM node:22-alpine AS build

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
RUN apk add --no-cache gettext
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/templates/default.conf.template
EXPOSE 80
ENV USERS_CONFIG_API_URL=http://users-config-backend:8080
ENV TRADING_CORE_API_URL=http://trading-core:8000
CMD ["/bin/sh", "-c", "envsubst '${USERS_CONFIG_API_URL} ${TRADING_CORE_API_URL}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
