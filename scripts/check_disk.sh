#!/usr/bin/env bash
# Warn before the disk fills up.
#
# Disk exhaustion is the failure that takes this system down quietly: clips accumulate,
# SQLite stops being able to write, and the first symptom anyone notices is that events
# stopped appearing. Catching it at 85% leaves room to act.
#
# Credentials are read from an env file rather than the crontab, so the bot token is not
# sitting in a file that other tools print.
#
#   /root/.smartcam-alert.env   (chmod 600)
#     TELEGRAM_BOT_TOKEN=123456:ABC...
#     TELEGRAM_CHAT_ID=987654321
#
# Other knobs:
#   DISK_ALERT_THRESHOLD  percent that triggers a warning   (default 85)
#   DISK_ALERT_PATH       filesystem to watch               (default /)
#   DISK_ALERT_STATE      marker to avoid repeating daily    (default /var/tmp/smartcam-disk)
set -euo pipefail

# shellcheck source=lib/alert.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/alert.sh"

THRESHOLD=${DISK_ALERT_THRESHOLD:-85}
WATCH=${DISK_ALERT_PATH:-/}
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

alert "$msg"

echo "$today" > "$STATE"

# Non-zero so cron mails it too, if this host has local mail configured.
exit 1
