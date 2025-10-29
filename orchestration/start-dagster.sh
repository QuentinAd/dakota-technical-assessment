#!/bin/bash
# Start Dagster services (daemon + webserver)
# This script ensures both the daemon (for executing runs) and webserver (for UI) are running

set -e

echo "Starting Dagster daemon..."
uv run dagster-daemon run -w /opt/dagster/app/dagster_project/workspace.yaml &

echo "Waiting for daemon to initialize..."
sleep 5

echo "Starting Dagster webserver..."
exec uv run dagster-webserver -h 0.0.0.0 -p 3000 -w /opt/dagster/app/dagster_project/workspace.yaml
