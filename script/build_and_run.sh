#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$ROOT_DIR/app/spot-app"
APP_BUNDLE="$APP_DIR/dist/spot.app"
CONFIG_DIR="${HOME}/Library/Application Support/spot"
CONFIG_FILE="$CONFIG_DIR/native-runtime.env"
PREFERRED_HOST="127.0.0.1"
PREFERRED_PORT="${SPOT_NATIVE_PORT:-8765}"
PYTHON_BIN="${SPOT_NATIVE_PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
RUNS_DIR="${SPOT_NATIVE_RUNS_DIR:-$CONFIG_DIR/runs}"
LOGS_DIR="${SPOT_NATIVE_LOGS_DIR:-$HOME/Library/Logs/spot}"
LOCKED_SSOT_PATH="${SPOT_LOCKED_SSOT_PATH:-$ROOT_DIR/ssot/ssot.json}"
ACCESS_CODE="${SPOT_LOCAL_ACCESS_CODE:-spot-local}"
AUTH_ENABLED="${SPOT_AUTH_ENABLED:-0}"

mkdir -p "$CONFIG_DIR" "$RUNS_DIR" "$LOGS_DIR"
chmod 700 "$CONFIG_DIR" "$RUNS_DIR" "$LOGS_DIR" >/dev/null 2>&1 || true

cat > "$CONFIG_FILE" <<EOF
SPOT_NATIVE_PYTHON_BIN="$PYTHON_BIN"
SPOT_NATIVE_RUNS_DIR="$RUNS_DIR"
SPOT_NATIVE_LOGS_DIR="$LOGS_DIR"
SPOT_LOCKED_SSOT_PATH="$LOCKED_SSOT_PATH"
SPOT_NATIVE_PORT="$PREFERRED_PORT"
SPOT_LOCAL_ACCESS_CODE="$ACCESS_CODE"
EOF
chmod 600 "$CONFIG_FILE" >/dev/null 2>&1 || true

pkill -x "spot" >/dev/null 2>&1 || true
pkill -f "launch-bundled-appliance.sh|uvicorn backend.main:app" >/dev/null 2>&1 || true

cd "$APP_DIR"
bash ./build-bundle.sh >/tmp/spot-app-build-path.txt

APP_PATH="$(tail -n 1 /tmp/spot-app-build-path.txt)"
if [[ ! -d "$APP_PATH" ]]; then
  echo "spot.app bundle was not created."
  exit 1
fi

/usr/bin/nohup /usr/bin/open -n "$APP_PATH" >/dev/null 2>&1 &

if [[ "${1:-}" == "--verify" ]]; then
  for _ in $(seq 1 60); do
    sleep 1
    BODY="$(/usr/bin/curl -fsS --max-time 2 "http://${PREFERRED_HOST}:${PREFERRED_PORT}/api/health" 2>/dev/null || true)"
    if [[ -n "$BODY" ]]; then
      echo "spot.app runtime ready on ${PREFERRED_HOST}:${PREFERRED_PORT}"
      exit 0
    fi
    if ! pgrep -fal "/Contents/MacOS/spot" >/dev/null && ! pgrep -x "spot" >/dev/null; then
      echo "spot.app launch did not leave a running native process."
      exit 1
    fi
  done
  echo "spot.app launched, but runtime readiness was not confirmed."
  exit 1
fi
