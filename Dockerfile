FROM nginx:1.27-alpine
RUN apk add --no-cache apache2-utils python3
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY docker/40-basic-auth.sh /docker-entrypoint.d/40-basic-auth.sh
RUN chmod +x /docker-entrypoint.d/40-basic-auth.sh
COPY site /usr/share/nginx/html
COPY market /app/market
EXPOSE 80
