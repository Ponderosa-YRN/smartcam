"""Unit tests for the phase-2 pure-logic modules (zones, auth, retention, analytics)."""
import os
import sys
import tempfile
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from smartcam.config import ZoneConfig, AuthConfig, AuthUser, hash_password
from smartcam.zones import ZoneTracker, point_in_polygon, in_allowed_window
from smartcam.detector import Detection
from smartcam.auth import authenticate
from smartcam.db import EventStore
from smartcam.analytics import build_report, Heatmap

# geometry
assert point_in_polygon(0.5, 0.5, [[0, 0], [1, 0], [1, 1], [0, 1]]) is True
assert point_in_polygon(1.5, 1.5, [[0, 0], [1, 0], [1, 1], [0, 1]]) is False
print("point_in_polygon OK")

# allowed window (fixed timestamps)
noon = datetime(2024, 1, 1, 12, 0, 0).timestamp()
night = datetime(2024, 1, 1, 3, 0, 0).timestamp()
assert in_allowed_window("06:00-22:00", noon) is True
assert in_allowed_window("06:00-22:00", night) is False
assert in_allowed_window("22:00-06:00", night) is True  # wraps midnight
print("in_allowed_window OK")

# occupancy + queue
z = ZoneConfig(id="lobby", name="Lobby", points=[[0, 0], [1, 0], [1, 1], [0, 1]], classes=["person"], max_occupancy=2)
zt = ZoneTracker([z], cooldown=0.0)
p1 = Detection(xyxy=[100, 100, 200, 400], cls=0, label="person", conf=0.9, track_id=1)
ev = zt.update([p1], time.time(), 400, 400)
assert zt.states[0].occupancy == 1 and not ev, ev
p2 = Detection(xyxy=[200, 100, 300, 400], cls=0, label="person", conf=0.9, track_id=2)
ev = zt.update([p1, p2], time.time(), 400, 400)
assert zt.states[0].occupancy == 2
assert any(e["type"] == "queue" for e in ev), ev
print("ZoneTracker occupancy/queue OK")

# loitering
zt2 = ZoneTracker([ZoneConfig(id="z", name="Z", points=[[0, 0], [1, 0], [1, 1], [0, 1]], classes=["person"], loiter_sec=0.2)], cooldown=0.0)
t0 = time.time()
zt2.update([p1], t0, 400, 400)
time.sleep(0.25)
ev = zt2.update([p1], time.time(), 400, 400)
assert any(e["type"] == "loitering" for e in ev), ev
print("ZoneTracker loitering OK")

# intrusion (restricted, outside window)
night_ts = datetime(2024, 1, 1, 3, 0, 0).timestamp()
zt3 = ZoneTracker([ZoneConfig(id="r", name="Roof", points=[[0, 0], [1, 0], [1, 1], [0, 1]], classes=["person"], restricted=True, allowed_window="06:00-22:00")], cooldown=0.0)
ev = zt3.update([p1], night_ts, 400, 400)
assert any(e["type"] == "intrusion" for e in ev), ev
print("ZoneTracker intrusion OK")

# auth
assert authenticate(AuthConfig(enabled=False), "x", "y") == "admin"
a2 = AuthConfig(enabled=True, users=[AuthUser(username="admin", password_hash=hash_password("pw"), role="admin")])
assert authenticate(a2, "admin", "pw") == "admin"
assert authenticate(a2, "admin", "wrong") is None
print("auth OK")

# report + heatmap
tmpdb = tempfile.mktemp(suffix=".db")
store = EventStore(tmpdb)
store.add_event({"camera_id": "c1", "camera_name": "Cam", "start_ts": time.time() - 100, "objects": ["person"], "event_type": "loitering", "summary": "Loitering in Lobby"})
rep = build_report(store, time.time() - 3600)
assert "loitering" in rep and "person" in rep, rep
h = Heatmap()
h.add_point(0.5, 0.5)
png = tempfile.mktemp(suffix=".png")
out = h.render(png)
assert os.path.exists(out)
store.close()
os.remove(tmpdb)
os.remove(out)
print("report + heatmap OK")

print("ALL FEATURE TESTS PASSED")
