#!/bin/bash
# Nightly reboot window: reboots the machine during 01:00-01:59 GMT (any timezone/DST safe).
# Runs hourly as a LaunchDaemon (root). With --force it reboots immediately regardless of hour
# (operator test path). Log: /Library/Logs/spot-nightly-reboot.log
LOG=/Library/Logs/spot-nightly-reboot.log
if [[ "${1:-}" == "--force" ]]; then
  echo "$(date -u +%FT%TZ) FORCED reboot (operator test)" >> "$LOG"
  shutdown -r +1
  exit 0
fi
utc_hour=$(date -u +%H)
if [[ "$utc_hour" == "01" ]]; then
  echo "$(date -u +%FT%TZ) scheduled nightly reboot (01:00 GMT window)" >> "$LOG"
  shutdown -r +1
fi
exit 0
