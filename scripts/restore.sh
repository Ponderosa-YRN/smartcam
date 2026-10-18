#!/usr/bin/env bash
# Restore, or verify, a SmartCam backup archive.
#
#   ./restore.sh --check <archive.tar.gz>   inspect only, touches nothing
#   ./restore.sh <archive.tar.gz>           restore into the running container
#
# Verification exists so the backup can be proven before it is needed. An unverified
# backup is a hope, not a backup.
set -euo pipefail

NAME=${NAME:-smartcam}
MODE=restore
if [ "${1:-}" = "--check" ]; then MODE=check; shift; fi
ARCHIVE=${1:?usage: restore.sh [--check] <archive.tar.gz>}

[ -f "$ARCHIVE" ] || { echo "FATAL: no such archive: $ARCHIVE"; exit 1; }

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
echo "==> extracting $ARCHIVE"
tar -xzf "$ARCHIVE" -C "$WORK"

[ -f "$WORK/events.db" ] || { echo "FATAL: archive has no events.db - not a SmartCam backup"; exit 1; }

echo "==> checking the database"
python3 - "$WORK/events.db" <<'PY'
import sqlite3, sys
db = sys.argv[1]
c = sqlite3.connect(db)
ok = c.execute("PRAGMA integrity_check").fetchone()[0]
print("    integrity_check:", ok)
if ok != "ok":
    sys.exit("FATAL: database in this archive is corrupt")
for t in ("events", "users", "tenants", "plates", "faces", "identities"):
    try:
        n = c.execute("SELECT COUNT(*) FROM " + t).fetchone()[0]
        print("    %-12s %d" % (t, n))
    except Exception as e:
        print("    %-12s (missing: %s)" % (t, e))
PY

for f in config.json .token_secret audit.log; do
  if [ -f "$WORK/$f" ]; then echo "    $f present"; else echo "    $f absent"; fi
done

if [ "$MODE" = "check" ]; then
  echo "=== archive OK. Nothing was changed. ==="
  exit 0
fi

echo
echo "This will REPLACE the live database and config in container '$NAME'."
read -r -p "Type the word restore to continue: " confirm
[ "$confirm" = "restore" ] || { echo "aborted"; exit 1; }

echo "==> stopping $NAME"
docker stop "$NAME" >/dev/null

echo "==> restoring"
docker cp "$WORK/events.db" "$NAME:/app/data/events.db"
for f in config.json .token_secret audit.log; do
  [ -f "$WORK/$f" ] && docker cp "$WORK/$f" "$NAME:/app/data/$f"
done
if [ -d "$WORK/clips" ]; then
  docker cp "$WORK/clips/." "$NAME:/app/data/clips" 2>/dev/null || true
fi
if [ -d "$WORK/thumbs" ]; then
  docker cp "$WORK/thumbs/." "$NAME:/app/data/thumbs" 2>/dev/null || true
fi

echo "==> starting $NAME"
docker start "$NAME" >/dev/null

echo "==> waiting for the API"
for _ in $(seq 1 30); do
  if [ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/api/health || true)" = "200" ]; then
    echo "=== restored and healthy ==="
    exit 0
  fi
  sleep 2
done

echo "FATAL: the API did not come up after the restore. Check: docker logs --tail 50 $NAME"
exit 1
