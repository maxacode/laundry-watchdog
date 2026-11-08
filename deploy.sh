#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
# shellcheck disable=SC1091
source .venv/bin/activate

FILES=(
  config_store.py
  error_log.py
  mpu6050.py
  wifi_connect.py
  notification.py
  webserver.py
  main.py
  config.json
)

for f in "${FILES[@]}"; do
  echo "Uploading $f"
  mpremote connect auto cp "$f" ":$f"
done

mpremote connect auto reset
echo "Deployed. Waiting for boot errors..."
sleep 4
./fetch_error_log.sh
echo "Onboard LED should blink every 2s when healthy."
