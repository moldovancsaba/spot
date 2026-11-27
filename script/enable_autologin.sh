#!/bin/bash
# One-time auto-login enabler. Run ONCE from Terminal (asks for your password):
#     sudo bash /Users/Shared/Projects/spot/script/enable_autologin.sh
#
# After the reboot the machine must reach the desktop WITHOUT a password prompt.
# If it still stops at the login screen, use the GUI path:
# System Settings > Users & Groups > Login Options > "Automatically log in as: chappie".
set -euo pipefail

FV="$(fdesetup status 2>/dev/null || true)"
if [[ "$FV" == *"On."* ]]; then
  echo "FileVault is ON - macOS hides/disables auto-login while FileVault is active."
  echo "To make reboots fully unattended: System Settings > Privacy & Security > FileVault > Turn Off."
  echo "Then re-run this script."
  exit 1
fi

defaults write /Library/Preferences/com.apple.loginwindow autoLoginUser -string chappie
echo "autoLoginUser = chappie written."
echo "NOTE: on recent macOS the System Settings GUI path is authoritative - verify with:"
echo "  defaults read /Library/Preferences/com.apple.loginwindow autoLoginUser"
echo "and test with a reboot: the desktop must appear with no password prompt."
