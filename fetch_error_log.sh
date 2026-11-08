#!/usr/bin/env bash
# Pull Pico error.log into the workspace and open it in Cursor's browser.
set -euo pipefail
cd "$(dirname "$0")"
# shellcheck disable=SC1091
source .venv/bin/activate

OUT="error.log"
HTML="error_log.html"
PORT=8765

echo "Fetching error.log from Pico..."
if mpremote connect auto cp :error.log "$OUT" 2>/dev/null; then
  echo "Saved $OUT"
else
  echo "(no error.log on device yet)" > "$OUT"
fi

{
  printf '%s\n' '<!DOCTYPE html><html><head><meta charset="utf-8">'
  printf '%s\n' '<meta http-equiv="refresh" content="15">'
  printf '%s\n' '<title>Pico error.log</title>'
  printf '%s\n' '<style>body{font:14px/1.45 ui-monospace,Menlo,monospace;margin:1.5rem;background:#111;color:#e8e8e8}'
  printf '%s\n' 'h1{font:600 1rem system-ui,sans-serif;color:#aaa}pre{white-space:pre-wrap;word-break:break-word}</style></head><body>'
  printf '%s\n' '<h1>Pico error.log</h1><pre>'
  sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g' "$OUT"
  printf '%s\n' '</pre></body></html>'
} > "$HTML"

# Prefer live Pico web UI when Wi-Fi IP is known; else local viewer.
VIEW_URL=""
IP="$(mpremote connect auto exec "from config_store import load_config; print(load_config().get('wifi_ip') or '')" 2>/dev/null | tr -d '\r' | tail -n1 || true)"
if [[ -n "${IP}" && "${IP}" != "None" ]]; then
  VIEW_URL="http://${IP}/api/errors"
fi

# Localhost fallback so Cursor browser can load the pulled file.
if ! lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  python -m http.server "$PORT" --bind 127.0.0.1 >/dev/null 2>&1 &
  echo $! > .error_log_server.pid
  sleep 0.3
fi
LOCAL_URL="http://127.0.0.1:${PORT}/${HTML}"
if [[ -z "${VIEW_URL}" ]]; then
  VIEW_URL="$LOCAL_URL"
fi

# Open log in editor + Simple Browser.
if command -v cursor >/dev/null 2>&1; then
  cursor -r -g "$OUT" >/dev/null 2>&1 || true
  cursor --open-url "vscode://vscode.simple-browser/show?url=${VIEW_URL}" >/dev/null 2>&1 \
    || open "$VIEW_URL"
elif command -v code >/dev/null 2>&1; then
  code -r -g "$OUT" >/dev/null 2>&1 || true
  code --open-url "vscode://vscode.simple-browser/show?url=${VIEW_URL}" >/dev/null 2>&1 \
    || open "$VIEW_URL"
else
  open "$VIEW_URL"
fi

echo "Browser: $VIEW_URL"
echo "Local mirror: $LOCAL_URL"
echo "----- error.log -----"
cat "$OUT"
echo "---------------------"
