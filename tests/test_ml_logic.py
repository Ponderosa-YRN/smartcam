"""Tests for ML-adjacent pure logic (no heavy model deps required)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from smartcam.alpr import _is_plate
from smartcam.config import AppConfig, SourceConfig, ZoneConfig, validate_config
from smartcam.face import FaceEngine
from smartcam.jobs import BoundedQueue
from smartcam.reid import ReidEngine


def test_cosine():
    assert FaceEngine.cosine([1, 0], [1, 0]) > 0.99
    assert FaceEngine.cosine([1, 0], [0, 1]) < 0.01
    assert ReidEngine.cosine([1, 1, 0], [1, 1, 0]) > 0.99
    assert ReidEngine.cosine([1, 0], [-1, 0]) < -0.99  # opposite vectors


def test_is_plate():
    assert _is_plate("LND123AB") is True
    assert _is_plate("ABC123") is True
    assert _is_plate("CAR") is False       # no digit
    assert _is_plate("1234") is False      # no letter
    assert _is_plate("A") is False         # too short


def test_gallery_matching():
    # ReID gallery matching = max cosine over the gallery
    gallery = [[1, 0, 0], [0, 1, 0]]
    emb = [1, 0.1, 0]
    best = max(ReidEngine.cosine(emb, g) for g in gallery)
    assert best > 0.9


def test_bounded_queue():
    q = BoundedQueue(maxsize=2)
    q.put(1)
    q.put(2)
    q.put(3)
    assert q.qsize() == 2
    assert q.get() == 2  # oldest (1) was dropped


def test_config_validation():
    assert validate_config(AppConfig()) == []
    bad = AppConfig(
        sources=[SourceConfig(id="", uri="")],
        zones=[ZoneConfig(id="z", points=[[0, 0], [1, 1]])],
    )
    errs = validate_config(bad)
    assert any("empty id" in e for e in errs)
    assert any("fewer than 3 points" in e for e in errs)


def test_db_store():
    import tempfile

    from smartcam.db import EventStore

    s = EventStore(tempfile.mktemp(suffix=".db"))
    eid = s.add_event({"camera_id": "c1", "objects": ["person"]})
    assert s.get_event(eid)["objects"] == ["person"]
    s.close()


def test_smart_search():
    import tempfile

    from smartcam.db import EventStore
    from smartcam.search import SmartSearch

    s = EventStore(tempfile.mktemp(suffix=".db"))
    s.add_event({"camera_id": "c1", "objects": ["person"], "event_type": "loitering"})
    search = SmartSearch(s, {0: "person"})
    assert len(search.run("person", limit=10)) == 1
    s.close()


def test_auth():
    from smartcam.auth import authenticate
    from smartcam.config import AuthConfig, AuthUser, hash_password

    a = AuthConfig(enabled=True, users=[AuthUser(username="admin", password_hash=hash_password("pw"), role="admin")])
    assert authenticate(a, "admin", "pw") == "admin"
    assert authenticate(a, "admin", "wrong") is None


def test_occupancy():
    from smartcam.config import AppConfig, SourceConfig
    from smartcam.pipeline import PipelineManager

    class FP:
        def __init__(self, counts):
            self.stats = {"object_counts": counts, "status": "running"}

        def health(self):
            return "healthy"

    m = PipelineManager.__new__(PipelineManager)
    m.cfg = AppConfig(sources=[SourceConfig(id="a", name="A"), SourceConfig(id="b", name="B")])
    m.pipelines = {"a": FP({"person": 3, "car": 2}), "b": FP({"person": 1, "car": 1, "truck": 1})}
    o = m.occupancy()
    assert o["people"] == 4
    assert o["vehicles"] == 4


def test_zones():
    from datetime import datetime

    from smartcam.zones import in_allowed_window, point_in_polygon

    assert point_in_polygon(0.5, 0.5, [[0, 0], [1, 0], [1, 1], [0, 1]]) is True
    noon = datetime(2024, 1, 1, 12, 0, 0).timestamp()
    night = datetime(2024, 1, 1, 3, 0, 0).timestamp()
    assert in_allowed_window("06:00-22:00", noon) is True
    assert in_allowed_window("06:00-22:00", night) is False


if __name__ == "__main__":
    test_cosine()
    test_is_plate()
    test_gallery_matching()
    test_bounded_queue()
    test_config_validation()
    print("ML LOGIC TESTS PASSED")
