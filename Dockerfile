FROM nginx:1.27-alpine
RUN apk add --no-cache apache2-utils
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY docker/40-basic-auth.sh /docker-entrypoint.d/40-basic-auth.sh
RUN chmod +x /docker-entrypoint.d/40-basic-auth.sh
COPY site /usr/share/nginx/html
EXPOSE 80
