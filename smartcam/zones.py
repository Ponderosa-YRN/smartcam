"""Zone geometry + per-zone state for loitering/queue/intrusion/parking."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .config import ZoneConfig
from .detector import Detection

# Zone events use a per-zone cooldown to avoid alert spam.
DEFAULT_COOLDOWN = 30.0


def point_in_polygon(x: float, y: float, poly: list[list[float]]) -> bool:
    n = len(poly)
    if n < 3:
        return False
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-9) + xi):
            inside = not inside
        j = i
    return inside


def in_allowed_window(win: str, ts: float | None = None) -> bool:
    """Return True if *ts* falls inside the "HH:MM-HH:MM" window (handles wrap)."""
    if not win or "-" not in win:
        return True
    try:
        a, b = win.split("-")
        now = datetime.fromtimestamp(ts or time.time())
        cur = now.hour * 60 + now.minute
        lo = _hm(a)
        hi = _hm(b)
    except ValueError:
        return True
    if lo <= hi:
        return lo <= cur < hi
    return cur >= lo or cur < hi


def _hm(s: str) -> int:
    h, m = s.strip().split(":")
    return int(h) * 60 + int(m)


@dataclass
class ZoneState:
    zone: ZoneConfig
    dwell: dict[int, float] = field(default_factory=dict)
    occupancy: int = 0
    vehicle_count: int = 0
    last_queue_alert: float = 0.0
    last_intrusion_alert: float = 0.0
    last_parking_alert: float = 0.0
    last_loiter_alert: float = 0.0


class ZoneTracker:
    """Evaluates all zones against the current detections and emits events."""

    def __init__(self, zones: list[ZoneConfig], cooldown: float = DEFAULT_COOLDOWN):
        self.states = [ZoneState(z) for z in zones]
        self.cooldown = cooldown

    def update(self, detections: list[Detection], ts: float, frame_w: int, frame_h: int) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for st in self.states:
            z = st.zone
            if not z.points:
                continue
            inside: list[Detection] = []
            for d in detections:
                if d.track_id is None:
                    continue
                if z.classes and d.label not in z.classes:
                    continue
                # Use the bottom-center (feet) point for membership, clamped
                # away from the 1.0 boundary so ray-casting is robust.
                x1, y1, x2, y2 = d.xyxy
                cx = min(0.999, max(0.0, (x1 + x2) / 2.0 / max(1, frame_w)))
                cy = min(0.999, max(0.0, y2 / max(1, frame_h)))
                if point_in_polygon(cx, cy, z.points):
                    inside.append(d)

            st.occupancy = len(inside)
            st.vehicle_count = len([d for d in inside if d.label in ("car", "truck", "bus", "motorcycle", "bicycle")])

            # dwell / loitering
            seen: set[int] = {d.track_id for d in inside}
            for tid in list(st.dwell):
                if tid not in seen:
                    st.dwell.pop(tid, None)
            for d in inside:
                if z.loiter_sec and d.track_id not in st.dwell:
                    st.dwell[d.track_id] = ts
                elif z.loiter_sec and d.track_id in st.dwell and (ts - st.dwell[d.track_id]) >= z.loiter_sec:
                    if ts - st.last_loiter_alert >= self.cooldown:
                        st.last_loiter_alert = ts
                        events.append({
                            "type": "loitering", "zone": z.name,
                            "note": f"Loitering in {z.name} (>{int(z.loiter_sec)}s)",
                            "objects": [d.label],
                        })

            # queue / crowd
            if z.max_occupancy and st.occupancy >= z.max_occupancy:
                if ts - st.last_queue_alert >= self.cooldown:
                    st.last_queue_alert = ts
                    events.append({
                        "type": "queue", "zone": z.name,
                        "note": f"{z.name} crowded: {st.occupancy} people (limit {z.max_occupancy})",
                        "objects": sorted({d.label for d in inside}),
                    })

            # restricted / intrusion
            if z.restricted and inside and not in_allowed_window(z.allowed_window, ts):
                if ts - st.last_intrusion_alert >= self.cooldown:
                    st.last_intrusion_alert = ts
                    events.append({
                        "type": "intrusion", "zone": z.name,
                        "note": f"Intrusion in restricted zone {z.name}",
                        "objects": sorted({d.label for d in inside}),
                    })

            # parking
            if z.parking and z.capacity is not None and st.vehicle_count >= z.capacity:
                if ts - st.last_parking_alert >= self.cooldown:
                    st.last_parking_alert = ts
                    events.append({
                        "type": "parking", "zone": z.name,
                        "note": f"{z.name} parking full: {st.vehicle_count}/{z.capacity} vehicles",
                        "objects": ["car", "truck"],
                    })

        return events

    def snapshot(self) -> list[dict[str, Any]]:
        out = []
        for st in self.states:
            z = st.zone
            out.append({
                "id": z.id, "name": z.name, "occupancy": st.occupancy,
                "vehicle_count": st.vehicle_count,
                "parking": z.parking, "capacity": z.capacity,
            })
        return out
