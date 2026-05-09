#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$PROJECT_DIR/../.." && pwd)"
APP_NAME="spot"
BUILD_DIR="$PROJECT_DIR/.build/debug"
BUNDLE_DIR="$PROJECT_DIR/dist"
APP_BUNDLE="$BUNDLE_DIR/$APP_NAME.app"
CORE_DIR_NAME="spot-core"
ICON_BUILD_DIR="$PROJECT_DIR/.build/icon-assets"
ICON_PATH="$ICON_BUILD_DIR/spot.icns"
LAUNCHER_PATH="$APP_BUNDLE/Contents/Resources/$CORE_DIR_NAME/bin/launch-bundled-appliance.sh"

cd "$PROJECT_DIR"
swift build
bash "$PROJECT_DIR/build-icon.sh" >/dev/null

rm -rf "$APP_BUNDLE" "$BUNDLE_DIR/Spot.app"
mkdir -p \
  "$APP_BUNDLE/Contents/MacOS" \
  "$APP_BUNDLE/Contents/Resources/$CORE_DIR_NAME/bin" \
  "$APP_BUNDLE/Contents/Resources/$CORE_DIR_NAME/backend" \
  "$APP_BUNDLE/Contents/Resources/$CORE_DIR_NAME/src" \
  "$APP_BUNDLE/Contents/Resources/$CORE_DIR_NAME/ssot"

cp "$BUILD_DIR/$APP_NAME" "$APP_BUNDLE/Contents/MacOS/$APP_NAME"
chmod +x "$APP_BUNDLE/Contents/MacOS/$APP_NAME"

rsync -a --delete \
  --exclude "__pycache__/" \
  --exclude ".pytest_cache/" \
  --exclude ".ruff_cache/" \
  "$REPO_ROOT/backend/" "$APP_BUNDLE/Contents/Resources/$CORE_DIR_NAME/backend/"
rsync -a --delete \
  --exclude "__pycache__/" \
  --exclude ".pytest_cache/" \
  --exclude ".ruff_cache/" \
  "$REPO_ROOT/src/" "$APP_BUNDLE/Contents/Resources/$CORE_DIR_NAME/src/"
rsync -a --delete \
  --exclude ".DS_Store" \
  "$REPO_ROOT/ssot/" "$APP_BUNDLE/Contents/Resources/$CORE_DIR_NAME/ssot/"
cp "$REPO_ROOT/requirements.txt" "$APP_BUNDLE/Contents/Resources/$CORE_DIR_NAME/requirements.txt"

cat > "$LAUNCHER_PATH" <<'EOF'
#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_DIR="${HOME}/Library/Application Support/spot"
CONFIG_FILE="$CONFIG_DIR/native-runtime.env"
RUNS_DIR_DEFAULT="$CONFIG_DIR/runs"
LOGS_DIR_DEFAULT="${HOME}/Library/Logs/spot"
SSOT_PATH="$CORE_ROOT/ssot/ssot.json"
PORT="${SPOT_NATIVE_PORT:-8765}"

mkdir -p "$CONFIG_DIR" "$RUNS_DIR_DEFAULT" "$LOGS_DIR_DEFAULT"

if [[ -f "$CONFIG_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$CONFIG_FILE"
fi

PYTHON_BIN="${SPOT_NATIVE_PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
  echo "Missing executable SPOT_NATIVE_PYTHON_BIN. Configure $CONFIG_FILE first." >&2
  exit 1
fi

RUNS_DIR="${SPOT_NATIVE_RUNS_DIR:-$RUNS_DIR_DEFAULT}"
LOGS_DIR="${SPOT_NATIVE_LOGS_DIR:-$LOGS_DIR_DEFAULT}"
AUTH_ENABLED="${SPOT_AUTH_ENABLED:-0}"
ACCESS_CODE="${SPOT_LOCAL_ACCESS_CODE:-}"
LOCKED_SSOT_PATH="${SPOT_LOCKED_SSOT_PATH:-$SSOT_PATH}"
PRODUCTION_MODE="${SPOT_PRODUCTION_MODE:-1}"

mkdir -p "$RUNS_DIR" "$LOGS_DIR"
cd "$CORE_ROOT"

if [[ "${SPOT_RUN_PREFLIGHT:-1}" == "1" ]]; then
  "$PYTHON_BIN" -m src.cli preflight \
    --ssot "$LOCKED_SSOT_PATH" \
    --runs-dir "$RUNS_DIR" \
    --port "$PORT"
fi

export RUNS_DIR="$RUNS_DIR"
export SPOT_AUTH_ENABLED="$AUTH_ENABLED"
export SPOT_PRODUCTION_MODE="$PRODUCTION_MODE"
export SPOT_LOCKED_SSOT_PATH="$LOCKED_SSOT_PATH"
if [[ -n "$ACCESS_CODE" ]]; then
  export SPOT_LOCAL_ACCESS_CODE="$ACCESS_CODE"
fi

exec "$PYTHON_BIN" -m uvicorn backend.main:app --host 127.0.0.1 --port "$PORT"
EOF
chmod +x "$LAUNCHER_PATH"

cp "$PROJECT_DIR/Info.plist" "$APP_BUNDLE/Contents/Info.plist"
cp "$ICON_PATH" "$APP_BUNDLE/Contents/Resources/spot.icns"
echo -n "APPL????" > "$APP_BUNDLE/Contents/PkgInfo"

codesign --force --deep --sign - "$APP_BUNDLE" >/dev/null 2>&1 || true

echo "$APP_BUNDLE"
