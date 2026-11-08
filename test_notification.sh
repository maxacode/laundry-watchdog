#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
# shellcheck disable=SC1091
source .venv/bin/activate

echo "Uploading notification deps..."
mpremote connect auto cp config_store.py :config_store.py
mpremote connect auto cp wifi_connect.py :wifi_connect.py
mpremote connect auto cp config.json :config.json
mpremote connect auto cp notification.py :notification.py
echo "Sending test COMPLETE webhook..."
mpremote connect auto run notification.py
