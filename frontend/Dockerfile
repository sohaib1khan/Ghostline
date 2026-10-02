# Build the static app, then serve it with nginx as a non-root user.
FROM node:26.10.0-alpine AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.28.3-alpine

# DECISION: the official image pins extra modules to nginx 1.28.3-r1, which
# blocks the patched 1.28.3 package. This server does not load those modules.
# Drop the pins, install the patched nginx, and upgrade the rest of Alpine.
RUN apk add --no-cache --upgrade apk-tools \
    && apk del \
        nginx-module-acme \
        nginx-module-geoip \
        nginx-module-image-filter \
        nginx-module-njs \
        nginx-module-xslt \
    && apk add --no-cache --upgrade nginx \
    && apk upgrade --no-cache --available \
    && mkdir -p /usr/share/nginx/html /tmp/client_temp /tmp/proxy_temp /tmp/fastcgi_temp /tmp/uwsgi_temp /tmp/scgi_temp \
    && chown -R nginx:nginx /usr/share/nginx/html /tmp/client_temp /tmp/proxy_temp /tmp/fastcgi_temp /tmp/uwsgi_temp /tmp/scgi_temp

COPY nginx.conf /etc/nginx/nginx.conf
COPY nginx-headers.conf /etc/nginx/ghostline-headers.conf
COPY --from=build --chown=nginx:nginx /app/dist /usr/share/nginx/html

USER nginx
EXPOSE 8080

# Skip the image entrypoint. It writes config as root, and this container does not.
ENTRYPOINT ["nginx"]
CMD ["-g", "daemon off;"]

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=5 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/ || exit 1
