#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
# shellcheck disable=SC1091
source .venv/bin/activate

# One mpremote session avoids reconnect races while main.py is running.
echo "Uploading notification deps and sending test COMPLETE webhook..."
mpremote connect auto \
  cp config_store.py :config_store.py \
  + cp error_log.py :error_log.py \
  + cp wifi_connect.py :wifi_connect.py \
  + cp config.json :config.json \
  + cp notification.py :notification.py \
  + run notification.py
