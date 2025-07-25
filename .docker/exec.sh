#!/usr/bin/env bash

docker exec -t qgis sh -c "cd /tests_directory && qgis_testrunner.sh infrastructure.test_runner.test_package"