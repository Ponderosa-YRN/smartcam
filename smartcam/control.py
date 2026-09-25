"""Lightweight cloud control plane (no ML / detection).

Used when SMART_CAM_CLOUD_ONLY=1: the cloud stores and serves events, alerts,
tenants, devices, and ingestion, while detection runs on edge boxes. This
manager mirrors just enough of PipelineManager's surface for the API, and it
imports no PyTorch/OpenCV/ultralytics, so the image is small and runs in ~256 MB.
"""
from __future__ import annotations

import types

from fastapi import HTTPException

from .db import EventStore


class ControlPlaneManager:
    def __init__(self, cfg):
        self.cfg = cfg
        cfg.ensure_dirs()
        self.store = EventStore(db_path=cfg.db_path, database_url=getattr(cfg, "database_url", "") or None)
        # No ML model in the cloud: class names are empty (SmartSearch has its
        # own fallback vocabulary), and there are no local pipelines.
        self.detector = types.SimpleNamespace(names={})
        self.pipelines = {}
        self.face_engine = None
        self.reid_engine = None
        self.jobs = None
        self.cfg.sources = []

    def occupancy(self) -> dict:
        return {"people": 0, "vehicles": 0, "entered": 0, "left": 0, "cameras": {}}

    def add_source(self, source):
        raise HTTPException(status_code=503, detail="source management is not available in cloud-only mode")

    def remove_source(self, source_id):
        raise HTTPException(status_code=503, detail="source management is not available in cloud-only mode")

    def stop_all(self):
        pass
