FROM nginx:1.27-alpine

COPY nginx.conf.template /etc/nginx/nginx.conf.template

CMD ["/bin/sh", "-c", "envsubst '$$NGINX_UPSTREAM_HOST $$NGINX_UPSTREAM_PORT' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf && exec nginx -g 'daemon off;'"]
