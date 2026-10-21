#!/usr/bin/env bash
# Is the site actually serving? Runs on the box, so it cannot report the box being
# unreachable - only that Caddy, the web tier or the API has stopped doing its job.
#
# Alerts go over the same Telegram bot the disk check uses.
#
#   /root/.smartcam-alert.env   (chmod 600)
#     TELEGRAM_BOT_TOKEN=...
#     TELEGRAM_CHAT_ID=...
#
# Knobs:
#   SITE_URL          page to fetch        (default https://agay.tech/)
#   SITE_EXPECT       phrase that proves the page rendered, not just that Caddy answered
#   SITE_API_URL      health endpoint      (default https://agay.tech/smartapi/api/health)
#   SITE_STATE        marker file          (default /var/tmp/smartcam-site)
#   SITE_REPEAT_SEC   re-alert while still down (default 6 hours)
set -euo pipefail

ENV_FILE=${DISK_ALERT_ENV_FILE:-/root/.smartcam-alert.env}
if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

URL=${SITE_URL:-https://agay.tech/}
EXPECT=${SITE_EXPECT:-Know what happened}
API_URL=${SITE_API_URL:-https://agay.tech/smartapi/api/health}
STATE=${SITE_STATE:-/var/tmp/smartcam-site}
REPEAT=${SITE_REPEAT_SEC:-21600}
TOKEN=${TELEGRAM_BOT_TOKEN:-}
CHAT=${TELEGRAM_CHAT_ID:-}

now=$(date +%s)
tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT

reason=""
check() {
  local url="$1" expect="$2" out
  out=$(curl -sS --max-time 15 -o "$tmp" -w '%{http_code}' "$url" 2>/dev/null || echo 000)
  if [ "$out" != "200" ]; then
    echo "$url returned HTTP $out"
    return 1
  fi
  if [ -n "$expect" ] && ! grep -qF -- "$expect" "$tmp"; then
    echo "$url answered 200 but the page did not render"
    return 1
  fi
  return 0
}

ok=1
if ! reason=$(check "$URL" "$EXPECT"); then ok=0; fi
if [ "$ok" = "1" ] && ! reason=$(check "$API_URL" "smartcam"); then ok=0; fi

prev_state=""
prev_ts=0
prev_reason=""
if [ -f "$STATE" ]; then
  IFS=$'\t' read -r prev_state prev_ts prev_reason < "$STATE" || true
fi
prev_ts=${prev_ts:-0}

send() {
  local msg="$1"
  echo "$(date -Is) $msg"
  if [ -n "$TOKEN" ] && [ -n "$CHAT" ]; then
    curl -fsS -m 10 -X POST "https://api.telegram.org/bot$TOKEN/sendMessage" \
      --data-urlencode "chat_id=$CHAT" \
      --data-urlencode "text=$msg" >/dev/null || echo "WARNING: could not deliver to Telegram" >&2
  else
    echo "NOTE: no Telegram credentials in $ENV_FILE" >&2
  fi
}

if [ "$ok" = "1" ]; then
  if [ "$prev_state" = "fail" ]; then
    mins=$(( (now - prev_ts) / 60 ))
    send "SmartCam: site is responding again (was down about ${mins} min)."
  fi
  printf 'ok\t%s\t\n' "$now" > "$STATE"
  exit 0
fi

if [ "$prev_state" != "fail" ]; then
  send "SmartCam: SITE DOWN - $reason"
elif [ $(( now - prev_ts )) -ge "$REPEAT" ]; then
  mins=$(( (now - prev_ts) / 3600 ))
  send "SmartCam: STILL DOWN after ${mins}h - $reason"
fi

printf 'fail\t%s\t%s\n' "$now" "$reason" > "$STATE"
exit 1
