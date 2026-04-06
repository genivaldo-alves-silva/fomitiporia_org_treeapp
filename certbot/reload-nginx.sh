#!/bin/sh
set -e

nginx_container="$(docker ps --filter "label=com.docker.compose.service=nginx" --format "{{.Names}}" | head -n 1)"
if [ -z "$nginx_container" ]; then
  echo "Nao foi possivel localizar o container do nginx para reload."
  exit 0
fi

docker exec "$nginx_container" nginx -s reload
