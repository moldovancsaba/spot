#!/bin/bash
# One-time installer for the nightly reboot job. Run ONCE from Terminal:
#     sudo bash /Users/Shared/Projects/spot/script/install_reboot_job.sh
# Grants exactly one narrow permission: running the reboot script without a password (for the operator
# test trigger). Nothing else is granted. Installs the LaunchDaemon and validates the sudoers file.
set -euo pipefail

SPOT=/Users/Shared/Projects/spot
USER_NAME="chappie"
SUDOERS="/etc/sudoers.d/spot-reboot"

cp "$SPOT/script/launchd/com.spot.nightly-reboot.plist" /Library/LaunchDaemons/
chmod 644 /Library/LaunchDaemons/com.spot.nightly-reboot.plist

printf '%s ALL=(root) NOPASSWD: %s/script/nightly_reboot.sh\n' "$USER_NAME" "$SPOT" > "$SUDOERS"
chmod 440 "$SUDOERS"
visudo -c >/dev/null

launchctl unload /Library/LaunchDaemons/com.spot.nightly-reboot.plist 2>/dev/null || true
launchctl load /Library/LaunchDaemons/com.spot.nightly-reboot.plist

echo "nightly reboot job installed"
launchctl list | grep nightly-reboot || true
