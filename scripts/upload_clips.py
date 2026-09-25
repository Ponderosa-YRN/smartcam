"""Upload existing local clips/thumbnails to S3 and update the DB.

Usage:
    python scripts/upload_clips.py --dry-run
    python scripts/upload_clips.py

Requires storage.provider = "s3" in config.json (or SMART_CAM_S3_* env vars)
and the boto3 package installed.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from smartcam.config import load_config
from smartcam.db import EventStore
from smartcam.storage import get_storage


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--config", default=None, help="path to config.json")
    args = ap.parse_args()

    cfg = load_config(args.config)
    if cfg.storage.provider != "s3":
        print("error: storage.provider must be 's3' (got " + cfg.storage.provider + ")")
        sys.exit(1)

    store = EventStore(cfg.db_path)
    storage = get_storage(cfg)
    uploaded = 0

    for ev in store.list_events(limit=100000):
        for field in ("clip_path", "thumb_path"):
            local = ev.get(field)
            if not local:
                continue
            p = Path(local)
            if not p.exists():
                continue
            if args.dry_run:
                print("would upload", field, p.name)
                uploaded += 1
                continue
            key = storage.put(str(p))
            store.update_event(ev["id"], **{field: key})
            uploaded += 1

    store.close()
    print("uploaded", uploaded, "objects" + (" (dry run)" if args.dry_run else ""))


if __name__ == "__main__":
    main()
