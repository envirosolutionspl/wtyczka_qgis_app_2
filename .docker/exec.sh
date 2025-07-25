#!/usr/bin/env bash

docker exec -t qgis sh -c "cd /tests_directory/wtyczka_qgis_app && qgis_testrunner.sh wtyczka_qgis_app.infrastructure.test_runner.test_package"