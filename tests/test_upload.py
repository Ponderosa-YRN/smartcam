"""Test the upload/assessment flow: add a single-pass source, run it, remove it."""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# isolate data dir so the test does not pollute the real data/
os.environ["SMART_CAM_DATA_DIR"] = tempfile.mkdtemp()

from smartcam.config import SourceConfig, load_config
from smartcam.pipeline import PipelineManager

cfg = load_config(None)
cfg.detection.conf = 0.3
cfg.detection.imgsz = 320
cfg.detection.frame_stride = 2
cfg.events.trigger_classes = ["person"]
cfg.events.cooldown_sec = 5.0
mgr = PipelineManager(cfg)

src = SourceConfig(id="upload_test", name="Upload test", uri="demo/demo.avi", enabled=True, loop=False)
sid = mgr.add_source(src)
assert sid in mgr.pipelines and any(s.id == sid for s in mgr.cfg.sources)
print("add_source OK")

mgr.start(sid)
deadline = time.time() + 120
while time.time() < deadline:
    p = mgr.pipelines[sid]
    if p.stats["status"] == "stopped" and p.stats["frames"] > 0:
        break
    time.sleep(2)
    print(f"status={p.stats['status']} frames={p.stats['frames']} fps={p.stats['fps']} events={mgr.store.count_events()}")

p = mgr.pipelines[sid]
n = mgr.store.count_events()
print(f"FINAL status={p.stats['status']} running={p.running} frames={p.stats['frames']} events={n}")
assert p.stats["status"] == "stopped", "single-pass should auto-stop"
assert p.running is False, "running flag should clear on auto-stop"
assert p.stats["frames"] > 0, "should have processed frames"
assert n > 0, "should have recorded events"

mgr.remove_source(sid)
assert sid not in mgr.pipelines
assert not any(s.id == sid for s in mgr.cfg.sources)
print("remove_source OK")
print("UPLOAD TEST PASSED")
