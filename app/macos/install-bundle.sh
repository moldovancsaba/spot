#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_DIR="$PROJECT_DIR/dist"
APP_NAME="spot"
SOURCE_BUNDLE="$BUNDLE_DIR/$APP_NAME.app"
TARGET_BUNDLE="/Applications/$APP_NAME.app"
STAGING_ROOT="${TMPDIR:-/tmp}spot-macos-install"
STAGED_BUNDLE="$STAGING_ROOT/$APP_NAME.app"

require_bundle_file() {
  local bundle="$1"
  local relative="$2"
  if [[ ! -e "$bundle/$relative" ]]; then
    echo "Missing required bundle path: $bundle/$relative" >&2
    exit 1
  fi
}

verify_bundle() {
  local bundle="$1"
  require_bundle_file "$bundle" "Contents/Info.plist"
  require_bundle_file "$bundle" "Contents/MacOS/spot"
  require_bundle_file "$bundle" "Contents/Resources/spot.icns"
  require_bundle_file "$bundle" "Contents/Resources/spot-core"
  require_bundle_file "$bundle" "Contents/Resources/spot-core/bin/launch-bundled-appliance.sh"

  local icon_name
  icon_name="$(/usr/bin/defaults read "$bundle/Contents/Info" CFBundleIconFile 2>/dev/null || true)"
  local exec_name
  exec_name="$(/usr/bin/defaults read "$bundle/Contents/Info" CFBundleExecutable 2>/dev/null || true)"

  if [[ "$icon_name" != "spot" ]]; then
    echo "Unexpected CFBundleIconFile in $bundle: $icon_name" >&2
    exit 1
  fi

  if [[ "$exec_name" != "spot" ]]; then
    echo "Unexpected CFBundleExecutable in $bundle: $exec_name" >&2
    exit 1
  fi
}

if [[ ! -d "$SOURCE_BUNDLE" ]]; then
  echo "Bundle not found: $SOURCE_BUNDLE" >&2
  echo "Run ./build-bundle.sh first." >&2
  exit 1
fi

verify_bundle "$SOURCE_BUNDLE"

mkdir -p "$STAGING_ROOT"
rm -rf "$STAGED_BUNDLE"
/usr/bin/rsync -a --delete "$SOURCE_BUNDLE/" "$STAGED_BUNDLE/"
verify_bundle "$STAGED_BUNDLE"

/usr/bin/pkill -x "spot" >/dev/null 2>&1 || true
/usr/bin/pkill -f "launch-bundled-appliance.sh|uvicorn backend.main:app" >/dev/null 2>&1 || true
/usr/bin/osascript -e 'tell application "spot" to quit' >/dev/null 2>&1 || true
/bin/sleep 1

if [[ -d "$TARGET_BUNDLE" ]]; then
  /bin/rm -rf "$TARGET_BUNDLE"
fi

/usr/bin/rsync -a --delete "$STAGED_BUNDLE/" "$TARGET_BUNDLE/"
verify_bundle "$TARGET_BUNDLE"
/usr/bin/touch "$TARGET_BUNDLE"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$TARGET_BUNDLE" >/dev/null 2>&1 || true
/usr/bin/killall Dock >/dev/null 2>&1 || true

echo "$TARGET_BUNDLE"
