#!/usr/bin/env bash
# Close the cleartext hole on the SmartCam API.
#
# Recreates the API container with port 8000 published on LOOPBACK ONLY, so Caddy (on
# the host network) can still reach it but the internet cannot talk to your API over
# plain HTTP.
#
# Safety gates - the script refuses to run rather than guess:
#   * refuses on host networking (port publishing would not apply)
#   * refuses unless /app/data is on a volume (recreating would destroy the database)
#   * reuses the EXACT image, env vars, volumes and restart policy of the live container
#   * keeps the original container intact (stopped) and restores it if anything fails
set -euo pipefail

NAME=smartcam
BACKUP=smartcam-old

fail() { echo; echo "FATAL: $1"; exit 1; }

docker inspect "$NAME" >/dev/null 2>&1 || fail "no container named '$NAME'"

NETMODE=$(docker inspect -f '{{.HostConfig.NetworkMode}}' "$NAME")
IMG=$(docker inspect -f '{{.Config.Image}}' "$NAME")
RESTART=$(docker inspect -f '{{.HostConfig.RestartPolicy.Name}}' "$NAME")
[ -n "$RESTART" ] || RESTART=unless-stopped

echo "container : $NAME"
echo "image     : $IMG"
echo "network   : $NETMODE"
echo "restart   : $RESTART"
echo
echo "volumes:"
docker inspect -f '{{range .Mounts}}  {{if eq .Type "volume"}}{{.Name}}{{else}}{{.Source}}{{end}} -> {{.Destination}}{{println}}{{end}}' "$NAME"

if [ "$NETMODE" = "host" ]; then
  fail "container uses host networking, so -p does not apply. Nothing was changed."
fi

if ! docker inspect -f '{{range .Mounts}}{{.Destination}}{{"\n"}}{{end}}' "$NAME" | grep -qx '/app/data'; then
  fail "/app/data is NOT on a volume, so the database lives inside the container and recreating it would destroy your data. Nothing was changed."
fi

echo
echo "env var names (values hidden):"
docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$NAME" | cut -d= -f1 | sed 's/^/  /'

ENV_ARGS=()
while IFS= read -r line; do
  if [ -n "$line" ]; then ENV_ARGS+=(-e "$line"); fi
done < <(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$NAME")

VOL_ARGS=()
while IFS= read -r spec; do
  if [ -n "$spec" ]; then VOL_ARGS+=(-v "$spec"); fi
done < <(docker inspect -f '{{range .Mounts}}{{if eq .Type "volume"}}{{.Name}}{{else}}{{.Source}}{{end}}:{{.Destination}}{{println}}{{end}}' "$NAME")

RUN_ARGS=(--name "$NAME" --restart "$RESTART")
if [ "${#ENV_ARGS[@]}" -gt 0 ]; then RUN_ARGS+=("${ENV_ARGS[@]}"); fi
if [ "${#VOL_ARGS[@]}" -gt 0 ]; then RUN_ARGS+=("${VOL_ARGS[@]}"); fi

echo
echo "==> stopping $NAME (a few seconds of downtime start here)"
docker stop "$NAME" >/dev/null
docker rename "$NAME" "$BACKUP"

PORT_ARGS=(-p 127.0.0.1:8000:8000)
if [ -f /proc/net/if_inet6 ]; then PORT_ARGS+=(-p "[::1]:8000:8000"); fi

echo "==> starting the replacement, published on loopback only"
if ! docker run -d "${RUN_ARGS[@]}" "${PORT_ARGS[@]}" "$IMG" >/dev/null 2>&1; then
  echo "note: IPv6 loopback publish failed; retrying with IPv4 loopback only"
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  PORT_ARGS=(-p 127.0.0.1:8000:8000)
  if ! docker run -d "${RUN_ARGS[@]}" "${PORT_ARGS[@]}" "$IMG" >/dev/null 2>&1; then
    docker rm -f "$NAME" >/dev/null 2>&1 || true
    docker rename "$BACKUP" "$NAME"
    docker start "$NAME" >/dev/null
    fail "the replacement would not start; the original container has been restored."
  fi
fi

echo "==> waiting for the API to answer on loopback"
for _ in $(seq 1 30); do
  if [ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/api/health || true)" = "200" ]; then break; fi
  sleep 2
done

v4=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/api/health || true)
v6=$(curl -s --max-time 5 -o /dev/null -w '%{http_code}' "http://[::1]:8000/api/health" 2>/dev/null || true)
api=$(curl -s -o /dev/null -w '%{http_code}' https://agay.tech/api/health || true)
web=$(curl -s -o /dev/null -w '%{http_code}' https://agay.tech/login || true)
ext=$(curl -s --max-time 6 -o /dev/null -w '%{http_code}' http://187.7.27.37:8000/api/health 2>/dev/null || true)

echo
echo "  loopback 127.0.0.1:8000 : $v4"
echo "  loopback [::1]:8000     : ${v6:-000}"
echo "  via Caddy /api/health   : $api"
echo "  via Caddy /login        : $web"
echo "  public 187.7.27.37:8000 : ${ext:-000}   <- 000 means correctly refused"

if [ "$v4" != "200" ] || [ "$api" != "200" ] || [ "$web" != "200" ]; then
  echo
  echo "==> health check failed; rolling back"
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  docker rename "$BACKUP" "$NAME"
  docker start "$NAME" >/dev/null
  fail "rolled back - the original container is running again."
fi

echo
echo "SUCCESS: your API is no longer reachable from the internet in cleartext."
echo "The previous container is kept, stopped, as '$BACKUP'."
echo "Once you have clicked around the dashboard, remove it with:  docker rm $BACKUP"
