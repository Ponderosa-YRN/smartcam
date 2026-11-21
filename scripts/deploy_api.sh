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

# The full image. A lean control-plane image was tried and removed: it carried no PyTorch,
# OpenCV or ultralytics, so import, camera management, face recognition and re-ID all
# answered 503 on it. Detection has to run somewhere, and for one VPS this is where.
if [ -r /proc/meminfo ]; then
  avail=$(awk '/MemAvailable/ {printf "%d", $2/1024}' /proc/meminfo)
  echo "    available memory: ${avail} MB (the build and CPU inference want ~1 GB free)"
fi
echo "==> building $IMAGE with the detection pipeline (this takes several minutes)"
docker build -f Dockerfile -t "$IMAGE" .

ENV_ARGS=()
while IFS= read -r line; do
  case "$line" in
    SMART_CAM_CONFIG=*) ;;   # replaced below
    # Dropped deliberately: api.Dockerfile bakes this in, and an inherited container
    # would otherwise carry it forward forever - rebuilding with the full image while
    # still running in control-plane mode, which looks like nothing changed.
    SMART_CAM_CLOUD_ONLY=*) ;;
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
# A backup from an earlier deploy that was never cleaned up makes the rename below fail,
# leaving the API stopped. Clear it first - it is superseded by the container we are
# about to keep.
docker rm -f "$BACKUP" >/dev/null 2>&1 || true
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

# Reported, but NOT fatal: the site is deliberately firewalled while it is dark, and an
# unreachable public URL says nothing about the container itself.
# The public path carries the /smartapi prefix that Caddy strips; probing /api/health hits
# the web tier and returns 404, which reads like a failed deploy when nothing is wrong.
api=$(curl -s -o /dev/null -w '%{http_code}' https://agay.tech/smartapi/api/health || true)

# Prove the NEW code is actually running. Nine bad logins for a throwaway username must
# end in 429; the old image would keep answering 401 forever. The throttle key is
# host|username, so this cannot lock out a real account. Probed on loopback so the check
# still works while the public URL is firewalled.
probe=000
for _ in $(seq 1 9); do
  probe=$(curl -s -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:8000/auth/login \
    -H 'Content-Type: application/json' \
    -d '{"username":"__deploy_probe__","password":"x"}' || true)
done

echo
echo "  API health (through Caddy)            : $api     (want 200; 000 while the site is dark)"
echo "  login throttle after 9 bad attempts   : $probe     (want 429)"

if [ "$probe" != "429" ]; then
  docker logs --tail 40 "$NAME" || true
  rollback "the new code is not running - the login throttle did not engage."
fi

echo
echo "SUCCESS. The previous container is kept, stopped, as '$BACKUP'."
echo "Once you have clicked around and are happy:  docker rm $BACKUP"
