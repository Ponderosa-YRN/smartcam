#!/usr/bin/env bash
# Rebuild + restart the SmartCam dashboard (Next.js) container.
#
# Usage on the VPS:   bash /root/smartcam/scripts/deploy_web.sh
#
# Deliberately does NOT touch the Caddyfile: routing changes are rare and touch the
# API too, so they stay a deliberate, validated, separate step.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

echo "==> pulling latest code"
git pull --ff-only

echo "==> building dashboard image"
docker build --build-arg GIT_SHA="$(git rev-parse --short HEAD)" -t smartcam-web ./frontend

echo "==> restarting dashboard container"
docker rm -f smartcam-web >/dev/null 2>&1 || true
docker run -d --name smartcam-web --restart unless-stopped -p 127.0.0.1:3000:3000 smartcam-web

echo "==> waiting for the dashboard to answer"
for _ in $(seq 1 30); do
  code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3000/login || true)
  if [ "$code" = "200" ]; then
    echo "OK - https://agay.tech is serving the new build"
    exit 0
  fi
  sleep 2
done

echo "FAILED - dashboard did not come up. Recent logs:"
docker logs --tail 40 smartcam-web
exit 1
