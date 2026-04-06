FROM certbot/certbot:latest

RUN apk add --no-cache docker-cli

COPY reload-nginx.sh /usr/local/bin/reload-nginx.sh
RUN chmod +x /usr/local/bin/reload-nginx.sh
