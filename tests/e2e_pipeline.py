"""End-to-end pipeline test on the downloaded demo clip.

Run (from the project root, after installing requirements):
    .venv\Scripts\python tests\e2e_pipeline.py
"""
import glob
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from smartcam.config import load_config
from smartcam.pipeline import PipelineManager

config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config_demo.json")
cfg = load_config(config_path)
mgr = PipelineManager(cfg)
sid = cfg.sources[0].id

print("starting pipeline on:", cfg.sources[0].uri)
mgr.start(sid)

deadline = time.time() + 150
reported_event = False
while time.time() < deadline:
    time.sleep(2)
    p = mgr.pipelines[sid]
    n = mgr.store.count_events()
    print(
        f"t={int(time.time() - (deadline - 150)):3d}s  events={n}  "
        f"status={p.stats['status']}  fps={p.stats['fps']}  objs={p.stats['active_objects']}"
    )
    if n > 0 and not reported_event:
        reported_event = True
        print("  -> first event recorded")

mgr.stop(sid)

n = mgr.store.count_events()
clips = glob.glob(str(cfg.clips_dir / "*.mp4")) + glob.glob(str(cfg.clips_dir / "*.avi"))
thumbs = glob.glob(str(cfg.thumbs_dir / "*.jpg"))
print(f"\nFINAL: events={n} clips={len(clips)} thumbnails={len(thumbs)}")
for ev in mgr.store.list_events(limit=10):
    print(f"  event #{ev['id']} objects={ev.get('objects')} dur={ev.get('duration')} clip={ev.get('clip_path')}")

assert n > 0, "no events detected — check that the demo clip downloaded and YOLO weights are available"
assert clips, "no clip files were written"
print("E2E PIPELINE TEST PASSED")
