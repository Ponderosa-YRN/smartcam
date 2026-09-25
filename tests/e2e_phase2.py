"""Phase-2 end-to-end test: zones, blur, heatmap on the demo clip."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from smartcam.config import load_config
from smartcam.pipeline import PipelineManager

config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config_phase2.json")
cfg = load_config(config_path)
mgr = PipelineManager(cfg)
sid = cfg.sources[0].id
mgr.start(sid)
print("started pipeline with", len(cfg.zones), "zone(s), blur:", cfg.privacy.blur_enabled)

deadline = time.time() + 40
while time.time() < deadline:
    time.sleep(3)
    p = mgr.pipelines[sid]
    print(f"events={mgr.store.count_events()} types={mgr.store.count_by_type()} zones={[(z['name'], z['occupancy']) for z in p.stats.get('zones', [])]} heat={p.heatmap.counts.sum():.0f}")

mgr.stop(sid)
n = mgr.store.count_events()
by = mgr.store.count_by_type()
heat = mgr.pipelines[sid].heatmap.counts.sum()
print("FINAL types:", by, "| heatmap points:", int(heat))

assert n > 0, "no events recorded"
assert heat > 0, "heatmap empty (no person positions accumulated)"
assert any(k in by for k in ("loitering", "queue", "detection")), by
print("E2E PHASE-2 PASSED")
