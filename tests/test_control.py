"""Cloud-only control-plane manager tests."""

import tempfile
from pathlib import Path

import pytest
from fastapi import HTTPException

from smartcam.config import AppConfig
from smartcam.control import ControlPlaneManager


def _cfg() -> AppConfig:
    return AppConfig(data_dir=Path(tempfile.mkdtemp()))


def test_control_plane_basics():
    m = ControlPlaneManager(_cfg())
    try:
        tid = m.store.create_tenant("hotel-a", "Hotel A")
        assert m.store.get_tenant(tid)["name"] == "Hotel A"
        assert m.pipelines == {}
        assert m.cfg.sources == []
        assert m.detector.names == {}
        assert m.face_engine is None and m.reid_engine is None
        assert m.occupancy() == {"people": 0, "vehicles": 0, "entered": 0, "left": 0, "cameras": {}}
    finally:
        m.store.close()


def test_control_plane_rejects_source_management():
    m = ControlPlaneManager(_cfg())
    try:
        with pytest.raises(HTTPException):
            m.add_source(None)
        with pytest.raises(HTTPException):
            m.remove_source("x")
    finally:
        m.store.close()
