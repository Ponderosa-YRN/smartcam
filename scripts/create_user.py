"""Create or update a SmartCam API user (strong scrypt hashing).

Usage:
    python scripts/create_user.py --username admin --password 'secret' --role admin
    python scripts/create_user.py --username viewer1 --password 'secret' --role viewer
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from smartcam.config import load_config
from smartcam.db import EventStore
from smartcam.security import hash_password

ROLES = ("admin", "security", "manager", "viewer")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--username", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--role", default="admin", choices=ROLES)
    ap.add_argument("--config", default=None, help="path to config.json (default: SMART_CAM_CONFIG or ./config.json)")
    args = ap.parse_args()

    cfg = load_config(args.config)
    store = EventStore(cfg.db_path)
    existing = store.get_user_by_username(args.username)
    if existing is not None:
        store.update_user(existing["id"], password_hash=hash_password(args.password), role=args.role)
        print("updated user", args.username, "(id " + str(existing["id"]) + ")")
    else:
        uid = store.create_user(args.username, hash_password(args.password), role=args.role)
        print("created user", args.username, "(id " + str(uid) + ")")
    store.close()


if __name__ == "__main__":
    main()
