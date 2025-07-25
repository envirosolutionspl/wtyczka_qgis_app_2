#!/usr/bin/env bash

docker exec -t qgis sh -c "cd /test && qgis_testrunner.sh infrastructure.test_runner.test_package"