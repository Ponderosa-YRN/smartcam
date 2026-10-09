#!/usr/bin/env bash
# Rebuild and restart the SmartCam API container.
#
# This is the heavier of the two deploy scripts, so it is defensive:
#   * refuses unless /app/data is on a volume (recreating would destroy the database)
#   * carries config.json across from the old container, because it lives INSIDE the
#     container and a naive recreate silently resets every camera and preference
#   * reuses the exact env vars and volumes of the live container
#   * keeps port 8000 on loopback only
#   * health-checks, and rolls back to the original container if anything fails
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAME=smartcam
BACKUP=smartcam-old
IMAGE=smartcam-api:latest
SAVED=/tmp/smartcam-config-backup.json

fail() { echo; echo "FATAL: $1"; exit 1; }

cd "$REPO_DIR"

docker inspect "$NAME" >/dev/null 2>&1 || fail "no container named '$NAME'"

NETMODE=$(docker inspect -f '{{.HostConfig.NetworkMode}}' "$NAME")
RESTART=$(docker inspect -f '{{.HostConfig.RestartPolicy.Name}}' "$NAME")
[ -n "$RESTART" ] || RESTART=unless-stopped

echo "container : $NAME"
echo "network   : $NETMODE"
echo "restart   : $RESTART"
echo

if [ "$NETMODE" = "host" ]; then
  fail "container uses host networking; -p would not apply. Nothing was changed."
fi

if ! docker inspect -f '{{range .Mounts}}{{.Destination}}{{"\n"}}{{end}}' "$NAME" | grep -qx '/app/data'; then
  fail "/app/data is NOT on a volume, so recreating would destroy the database. Nothing was changed."
fi

echo "==> pulling latest code"
git pull --ff-only

echo "==> saving config.json out of the running container"
docker cp "$NAME:/app/config.json" "$SAVED" 2>/dev/null || echo "    (no config.json yet - will start from defaults)"

echo "==> building $IMAGE (this takes a few minutes)"
docker build -f api.Dockerfile -t "$IMAGE" .

ENV_ARGS=()
while IFS= read -r line; do
  case "$line" in
    SMART_CAM_CONFIG=*) ;;   # replaced below
    "") ;;
    *) ENV_ARGS+=(-e "$line") ;;
  esac
done < <(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$NAME")

VOL_ARGS=()
while IFS= read -r spec; do
  if [ -n "$spec" ]; then VOL_ARGS+=(-v "$spec"); fi
done < <(docker inspect -f '{{range .Mounts}}{{if eq .Type "volume"}}{{.Name}}{{else}}{{.Source}}{{end}}:{{.Destination}}{{println}}{{end}}' "$NAME")

RUN_ARGS=(--name "$NAME" --restart "$RESTART")
if [ "${#ENV_ARGS[@]}" -gt 0 ]; then RUN_ARGS+=("${ENV_ARGS[@]}"); fi
if [ "${#VOL_ARGS[@]}" -gt 0 ]; then RUN_ARGS+=("${VOL_ARGS[@]}"); fi
# Keep the config on the volume so it survives the NEXT rebuild too.
RUN_ARGS+=(-e "SMART_CAM_CONFIG=/app/data/config.json")

PORT_ARGS=(-p 127.0.0.1:8000:8000)
if [ -f /proc/net/if_inet6 ]; then PORT_ARGS+=(-p "[::1]:8000:8000"); fi

echo
echo "==> stopping $NAME (a few seconds of downtime start here)"
docker stop "$NAME" >/dev/null
docker rename "$NAME" "$BACKUP"

rollback() {
  echo "==> rolling back to the previous container"
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  docker rename "$BACKUP" "$NAME"
  docker start "$NAME" >/dev/null
  fail "$1"
}

if ! docker run -d "${RUN_ARGS[@]}" "${PORT_ARGS[@]}" "$IMAGE" >/dev/null 2>&1; then
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  PORT_ARGS=(-p 127.0.0.1:8000:8000)
  docker run -d "${RUN_ARGS[@]}" "${PORT_ARGS[@]}" "$IMAGE" >/dev/null 2>&1 \
    || rollback "the replacement would not start."
fi

if [ -f "$SAVED" ]; then
  docker cp "$SAVED" "$NAME:/app/data/config.json" >/dev/null 2>&1 || true
  docker restart "$NAME" >/dev/null
fi

echo "==> waiting for the API"
ok=0
for _ in $(seq 1 40); do
  if [ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/api/health || true)" = "200" ]; then ok=1; break; fi
  sleep 2
done
[ "$ok" = "1" ] || { docker logs --tail 40 "$NAME" || true; rollback "the API did not come up."; }

api=$(curl -s -o /dev/null -w '%{http_code}' https://agay.tech/api/health || true)
cfg=$(curl -s -o /dev/null -w '%{http_code}' https://agay.tech/smartapi/api/config || true)

echo
echo "  API health                     : $api   (want 200)"
echo "  /api/config without a token    : $cfg   (want 401)"

if [ "$api" != "200" ]; then
  docker logs --tail 40 "$NAME" || true
  rollback "the API is not healthy through Caddy."
fi

echo
echo "SUCCESS. The previous container is kept, stopped, as '$BACKUP'."
echo "Once you have clicked around and are happy:  docker rm $BACKUP"
