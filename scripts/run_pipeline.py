"""Headless pipeline runner: detect/track/record/notify without the web UI.

Usage:
    python scripts/run_pipeline.py            # uses config.json (or defaults)
    python scripts/run_pipeline.py --config path/to/config.json
"""
from __future__ import annotations

import argparse
import time

from smartcam.config import load_config
from smartcam.pipeline import PipelineManager
from smartcam.utils import setup_logging


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=None, help="path to config.json")
    args = ap.parse_args()

    cfg = load_config(args.config)
    setup_logging(cfg.data_dir)
    mgr = PipelineManager(cfg)
    print(f"Starting {len(mgr.pipelines)} source(s). Press Ctrl+C to stop.")
    mgr.start_all()
    try:
        while True:
            time.sleep(3)
            for sid, p in mgr.pipelines.items():
                s = p.stats
                print(
                    f"[{sid}] status={s['status']} fps={s['fps']} "
                    f"frames={s['frames']} objects={s['active_objects']}"
                )
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        mgr.stop_all()
        print("Stopped.")


if __name__ == "__main__":
    main()
