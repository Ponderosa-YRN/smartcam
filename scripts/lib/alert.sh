#!/usr/bin/env bash
# Shared alerting for the health checks. Sourced, never executed directly.
#
# Credentials come from an env file rather than the crontab, so the bot token is not in a
# file other tools print.
#
#   /root/.smartcam-alert.env   (chmod 600)
#     TELEGRAM_BOT_TOKEN=123456:ABC...
#     TELEGRAM_CHAT_ID=987654321
#
# Override the path with DISK_ALERT_ENV_FILE, which both checks already honoured.

ALERT_ENV_FILE=${DISK_ALERT_ENV_FILE:-/root/.smartcam-alert.env}
if [ -f "$ALERT_ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$ALERT_ENV_FILE"
  set +a
fi

TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN:-}
TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID:-}

# alert "<message>" - log it, then deliver to Telegram when credentials are configured.
alert() {
  echo "$(date -Is) $1"
  if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
    curl -fsS -m 10 -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
      --data-urlencode "chat_id=$TELEGRAM_CHAT_ID" \
      --data-urlencode "text=$1" >/dev/null \
      || echo "WARNING: could not deliver the alert to Telegram" >&2
  else
    echo "NOTE: no Telegram credentials in $ALERT_ENV_FILE, so nothing was sent beyond this log line." >&2
  fi
}
