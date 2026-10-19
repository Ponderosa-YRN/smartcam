#!/usr/bin/env bash
# Warn before the disk fills up.
#
# Disk exhaustion is the failure that takes this system down quietly: clips accumulate,
# SQLite stops being able to write, and the first symptom anyone notices is that events
# stopped appearing. Catching it at 85% leaves room to act.
#
# Environment:
#   DISK_ALERT_THRESHOLD  percent that triggers a warning      (default 85)
#   DISK_ALERT_PATH       filesystem to watch                  (default /)
#   DISK_ALERT_URL        where to POST the warning, e.g. an ntfy topic URL.
#                         Leave it unset and the script still logs and exits non-zero.
#   DISK_ALERT_STATE      file used to avoid repeating daily   (default /var/tmp/smartcam-disk)
set -euo pipefail

THRESHOLD=${DISK_ALERT_THRESHOLD:-85}
WATCH=${DISK_ALERT_PATH:-/}
URL=${DISK_ALERT_URL:-}
STATE=${DISK_ALERT_STATE:-/var/tmp/smartcam-disk}

usage=$(df -P "$WATCH" | awk 'NR==2 {gsub("%","",$5); print $5}')
today=$(date +%F)

if [ -z "$usage" ]; then
  echo "ERROR: could not read disk usage for $WATCH" >&2
  exit 2
fi

if [ "$usage" -lt "$THRESHOLD" ]; then
  # Recovered. Clear the marker so a future breach is reported immediately.
  rm -f "$STATE"
  exit 0
fi

# One warning per day, not one per hour, so the alert stays meaningful.
if [ -f "$STATE" ] && [ "$(cat "$STATE")" = "$today" ]; then
  exit 0
fi

free=$(df -h "$WATCH" | awk 'NR==2 {print $4}')
msg="SmartCam: disk $WATCH is ${usage}% full (warning at ${THRESHOLD}%), $free free on $(hostname)"

echo "$(date -Is) $msg"

if [ -n "$URL" ]; then
  if ! curl -fsS -m 10 -d "$msg" "$URL" >/dev/null; then
    echo "WARNING: could not deliver the alert to $URL" >&2
  fi
else
  echo "NOTE: DISK_ALERT_URL is unset, so nothing was sent - only this log entry exists." >&2
fi

echo "$today" > "$STATE"

# Non-zero so cron mails it too, if this host has local mail configured.
exit 1
