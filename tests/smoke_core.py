"""Dependency-free smoke test for config, db, and search (plain python)."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from smartcam.config import load_config, save_config
from smartcam.db import EventStore
from smartcam.search import SmartSearch

# config defaults
cfg = load_config(os.path.join(tempfile.gettempdir(), "does_not_exist.json"))
assert cfg.detection.model == "yolov8n.onnx", cfg.detection.model
assert cfg.sources[0].uri == "0"
assert "person" in cfg.events.trigger_classes
print("config defaults OK")

# save/load round trip
tmp = tempfile.mktemp(suffix=".json")
save_config(cfg, tmp)
cfg2 = load_config(tmp)
assert cfg2.detection.conf == cfg.detection.conf
assert cfg2.sources[0].id == cfg.sources[0].id
os.remove(tmp)
print("config round-trip OK")

# db
tmpdb = tempfile.mktemp(suffix=".db")
store = EventStore(tmpdb)
eid = store.add_event({
    "camera_id": "c1", "camera_name": "Cam", "start_ts": 1000.0,
    "objects": ["person", "car"], "top_object": "person", "track_ids": [1, 2],
})
ev = store.get_event(eid)
assert ev["objects"] == ["person", "car"], ev["objects"]
assert ev["track_ids"] == [1, 2]
store.update_event(eid, summary="A person walked by", duration=3.2)
ev = store.get_event(eid)
assert ev["summary"] == "A person walked by"
assert store.search(["person"], limit=10)[0]["id"] == eid
assert store.count_events() == 1
print("db OK")

# search parse + run
s = SmartSearch(store, {0: "person", 1: "car"})
p = s.parse("person at night")
assert p["classes"] == ["person"], p
assert p["tod"] == (20, 5), p
p2 = s.parse("car yesterday")
assert p2["classes"] == ["car"] and p2["date_range"] is not None
res = s.run("person", limit=10)
assert len(res) == 1
print("search OK")

store.close()
os.remove(tmpdb)
print("ALL CORE SMOKE TESTS PASSED")
