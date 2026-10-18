#!/usr/bin/env bash
# Nightly backup of the SmartCam control plane.
#
# The database is copied with SQLite's own VACUUM INTO, which writes a consistent
# snapshot while the API keeps running - a plain file copy of a live SQLite database
# can capture a half-written page and restore as corrupt.
#
# Environment:
#   BACKUP_DIR     where archives are staged        (default /root/smartcam-backups)
#   BACKUP_KEEP    days to retain                   (default 14)
#   BACKUP_MEDIA   1 to include clips + thumbnails  (default 1)
#   BACKUP_REMOTE  rclone target for the off-site copy, e.g. b2:smartcam-backups
#   BACKUP_REMOTE_KEEP  days to keep archives remotely (default 30)
set -euo pipefail

NAME=${NAME:-smartcam}
BACKUP_DIR=${BACKUP_DIR:-/root/smartcam-backups}
KEEP_DAYS=${BACKUP_KEEP:-14}
WITH_MEDIA=${BACKUP_MEDIA:-1}
REMOTE=${BACKUP_REMOTE:-}
REMOTE_KEEP_DAYS=${BACKUP_REMOTE_KEEP:-30}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)

mkdir -p "$BACKUP_DIR"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

echo "=== SmartCam backup $STAMP ==="

docker inspect "$NAME" >/dev/null 2>&1 || { echo "FATAL: no container named $NAME"; exit 1; }

echo "==> snapshotting the database"
docker exec "$NAME" python -c "import sqlite3; sqlite3.connect('/app/data/events.db', timeout=30).execute(\"VACUUM INTO '/app/data/.backup-snapshot.db'\")"
docker cp "$NAME:/app/data/.backup-snapshot.db" "$WORK/events.db" >/dev/null
docker exec "$NAME" rm -f /app/data/.backup-snapshot.db

echo "==> copying config and secrets"
for f in config.json .token_secret audit.log; do
  if docker cp "$NAME:/app/data/$f" "$WORK/$f" >/dev/null 2>&1; then
    echo "    $f"
  else
    echo "    ($f absent, skipped)"
  fi
done

if [ "$WITH_MEDIA" = "1" ]; then
  echo "==> copying media (clips + thumbnails)"
  docker cp "$NAME:/app/data/clips" "$WORK/clips" >/dev/null 2>&1 || echo "    (no clips dir)"
  docker cp "$NAME:/app/data/thumbs" "$WORK/thumbs" >/dev/null 2>&1 || echo "    (no thumbs dir)"
fi

ARCHIVE="$BACKUP_DIR/smartcam-$STAMP.tar.gz"
echo "==> writing $ARCHIVE"
tar -czf "$ARCHIVE" -C "$WORK" .
echo "    $(du -h "$ARCHIVE" | cut -f1)"

echo "==> pruning archives older than $KEEP_DAYS days"
find "$BACKUP_DIR" -name 'smartcam-*.tar.gz' -mtime +"$KEEP_DAYS" -print -delete || true

if [ -n "$REMOTE" ]; then
  command -v rclone >/dev/null || { echo "FATAL: BACKUP_REMOTE is set but rclone is not installed"; exit 1; }
  echo "==> uploading to $REMOTE"
  rclone copy "$ARCHIVE" "$REMOTE" --quiet
  echo "    uploaded"
  # rclone copy only ever adds. Without this the remote grows without limit and the
  # storage bill climbs quietly forever.
  echo "==> pruning remote archives older than $REMOTE_KEEP_DAYS days"
  rclone delete "$REMOTE" --min-age "${REMOTE_KEEP_DAYS}d" --include 'smartcam-*.tar.gz' --quiet || true
else
  echo "WARNING: BACKUP_REMOTE is not set, so this copy is on the same machine as the data."
  echo "         That protects against mistakes, not against losing the VPS."
fi

echo "=== done: $ARCHIVE ==="
