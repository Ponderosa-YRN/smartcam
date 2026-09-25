"""Data retention: purge clips/thumbnails/records older than N days."""
from __future__ import annotations

import logging
import os
import time

from .config import AppConfig
from .db import EventStore

log = logging.getLogger("smartcam.retention")


def purge(config: AppConfig, store: EventStore) -> int:
    days = config.retention.retention_days
    if days <= 0:
        return 0
    cutoff = time.time() - days * 86400
    paths = store.purge_older_than(cutoff)
    removed = 0
    for p in paths["clips"] + paths["thumbs"]:
        if not p:
            continue
        try:
            if os.path.exists(p):
                os.remove(p)
                removed += 1
        except OSError as exc:  # noqa: BLE001
            log.warning("retention remove failed: %s", exc)
    if removed:
        log.info("retention purged %d file(s)", removed)
    return removed
