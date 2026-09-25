"""Foot-traffic heatmaps and incident reports."""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from .db import EventStore
from .utils import ts_to_iso


class Heatmap:
    """Accumulates normalized track positions into a grid and renders an image."""

    def __init__(self, grid_w: int = 72, grid_h: int = 40):
        self.grid_w = grid_w
        self.grid_h = grid_h
        self.counts = np.zeros((grid_h, grid_w), dtype=np.float32)

    def add_point(self, nx: float, ny: float) -> None:
        gx = min(self.grid_w - 1, max(0, int(nx * self.grid_w)))
        gy = min(self.grid_h - 1, max(0, int(ny * self.grid_h)))
        self.counts[gy, gx] += 1.0

    def reset(self) -> None:
        self.counts.fill(0.0)

    def render(self, path: str | Path) -> Path:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = self.counts
        if data.max() > 0:
            data = data / data.max()
        fig, ax = plt.subplots(figsize=(9, 5), dpi=100)
        ax.imshow(data, cmap="turbo", origin="upper", aspect="auto")
        ax.set_title("Foot-traffic heatmap")
        ax.axis("off")
        fig.tight_layout(pad=0.2)
        fig.savefig(p, bbox_inches="tight")
        plt.close(fig)
        return p


def render_occupancy_chart(samples: list[dict[str, Any]], path: str | Path) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    samples = sorted(samples, key=lambda s: s.get("ts", 0))
    if not samples:
        fig, ax = plt.subplots(figsize=(10, 4), dpi=100)
        ax.text(0.5, 0.5, "No occupancy data yet", ha="center", va="center")
        ax.axis("off")
        fig.savefig(p, bbox_inches="tight")
        plt.close(fig)
        return p
    x = list(range(len(samples)))
    people = [s.get("people", 0) for s in samples]
    vehicles = [s.get("vehicles", 0) for s in samples]
    fig, ax = plt.subplots(figsize=(10, 4), dpi=100)
    ax.bar(x, people, label="People", color="#4f8bff")
    ax.bar(x, vehicles, bottom=people, label="Vehicles", color="#ff8b4f")
    step = max(1, len(x) // 8)
    ax.set_xticks(x[::step])
    ax.set_xticklabels([ts_to_iso(samples[i]["ts"])[11:16] for i in range(0, len(x), step)], fontsize=8)
    ax.set_title("Occupancy over time (people + vehicles)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    return p


def build_report(store: EventStore, since_ts: float, interval: str = "daily") -> str:
    """Produce a human-readable incident report for a time window."""
    events = store.list_events(limit=1000, since=since_ts, order="ASC")
    by_type: dict[str, int] = {}
    by_camera: dict[str, int] = {}
    objs: dict[str, int] = {}
    for e in events:
        t = e.get("event_type") or "detection"
        by_type[t] = by_type.get(t, 0) + 1
        cam = e.get("camera_name") or e.get("camera_id") or "unknown"
        by_camera[cam] = by_camera.get(cam, 0) + 1
        for o in (e.get("objects") or []):
            objs[o] = objs.get(o, 0) + 1

    lines = [f"SmartCam {interval} incident report", f"Period: {ts_to_iso(since_ts)} -> {ts_to_iso(time.time())}", ""]
    lines.append(f"Total events: {len(events)}")
    lines.append("")
    lines.append("By event type:")
    for k, v in sorted(by_type.items(), key=lambda kv: -kv[1]):
        lines.append(f"  - {k}: {v}")
    lines.append("")
    lines.append("By camera:")
    for k, v in sorted(by_camera.items(), key=lambda kv: -kv[1]):
        lines.append(f"  - {k}: {v}")
    if objs:
        lines.append("")
        lines.append("Top detected objects:")
        for k, v in sorted(objs.items(), key=lambda kv: -kv[1])[:10]:
            lines.append(f"  - {k}: {v}")
    return "\n".join(lines)
