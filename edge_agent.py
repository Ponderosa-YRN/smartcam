"""Edge agent: run detection locally and stream results to the SmartCam cloud.

The agent reuses the full local pipeline (CameraPipeline / PipelineManager) so an
edge box does the ML work on-site, keeps a local SQLite store as a resumable
buffer, and periodically pushes new events, occupancy samples, and their
clip/thumbnail files to the cloud using a device token (Admin -> Edge devices).

Usage:
    .venv\\Scripts\\python edge_agent.py --api-url http://cloud-host:8000 --token scd_1.xxx [--config config.json] [--interval 15]
"""
from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

from smartcam.client import ApiClient
from smartcam.config import load_config
from smartcam.pipeline import PipelineManager

log = logging.getLogger("edge_agent")

STATE_FILE = ".edge_state.json"


def _load_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"last_event_id": 0, "last_occ_id": 0}


def _save_state(path: Path, state: dict) -> None:
    path.write_text(json.dumps(state), encoding="utf-8")


def _sync(client: ApiClient, mgr: PipelineManager, state: dict) -> int:
    synced = 0

    events = mgr.store.list_events_since_id(state["last_event_id"], limit=500)
    if events:
        payload = [
            {
                "camera_id": e.get("camera_id"),
                "camera_name": e.get("camera_name"),
                "start_ts": e.get("start_ts"),
                "end_ts": e.get("end_ts"),
                "duration": e.get("duration"),
                "objects": e.get("objects") or [],
                "top_object": e.get("top_object"),
                "track_ids": e.get("track_ids") or [],
                "max_conf": e.get("max_conf"),
                "event_type": e.get("event_type"),
                "summary": e.get("summary"),
            }
            for e in events
        ]
        created = client.ingest_events(payload)
        if created is None:
            log.warning("event ingest failed; will retry next cycle")
            return synced
        cloud_ids = created.get("created", [])
        for e, cid in zip(events, cloud_ids):
            clip = e.get("clip_path")
            thumb = e.get("thumb_path")
            if (clip and Path(clip).exists()) or (thumb and Path(thumb).exists()):
                try:
                    client.ingest_media(cid, clip, thumb)
                except Exception as exc:
                    log.warning("media upload failed for event %s: %s", cid, exc)
        state["last_event_id"] = events[-1]["id"]
        synced += len(events)

    occ = mgr.store.list_occupancy_since_id(state["last_occ_id"], limit=500)
    if occ:
        samples = [{"ts": o["ts"], "people": o["people"], "vehicles": o["vehicles"]} for o in occ]
        if client.ingest_occupancy(samples) is None:
            log.warning("occupancy ingest failed; will retry next cycle")
            return synced
        state["last_occ_id"] = occ[-1]["id"]
        synced += len(occ)

    return synced


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    ap = argparse.ArgumentParser(description="SmartCam edge agent")
    ap.add_argument("--api-url", required=True, help="Cloud API base URL")
    ap.add_argument("--token", required=True, help="Device token from Admin -> Edge devices")
    ap.add_argument("--config", default=None, help="Path to a SmartCam config JSON")
    ap.add_argument("--interval", type=float, default=15.0, help="Sync interval in seconds")
    ap.add_argument("--state", default=STATE_FILE, help="Local sync state file")
    args = ap.parse_args()

    cfg = load_config(args.config)
    mgr = PipelineManager(cfg)
    mgr.start_all()
    log.info("edge agent started: %d source(s), pushing to %s", len(cfg.sources), args.api_url)

    client = ApiClient(args.api_url)
    client.set_device_token(args.token)

    state_path = Path(args.state)
    state = _load_state(state_path)

    while True:
        time.sleep(args.interval)
        try:
            n = _sync(client, mgr, state)
            client.heartbeat()
            _save_state(state_path, state)
            if n:
                log.info("synced %d records", n)
        except Exception as exc:
            log.warning("sync failed: %s", exc)


if __name__ == "__main__":
    main()
