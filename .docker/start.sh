#!/usr/bin/env bash

docker compose -f docker-compose.yml up -d --force-recreate
echo 'Wait 10 seconds'
sleep 10
echo 'Installation of the plugin'
docker exec -t qgis sh -c "qgis_setup.sh wtyczka_qgis_app"
# docker exec -t qgis sh -c "pip3 install webdavclient3"
docker exec -t qgis sh -c "pip3 install psycopg[binary]"
echo 'Containers are running'