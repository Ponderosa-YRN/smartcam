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

# A table counts as seated only after somebody has been inside it this long, so a waiter
# walking past does not flip it red. It frees again only after being empty this long, so a
# single missed frame does not clear a table that is genuinely occupied.
TABLE_SEATED_CONFIRM_SEC = 20.0
TABLE_FREE_CONFIRM_SEC = 30.0


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
    # Table tracking. occupied_since survives brief dropouts; seated_since is only set once
    # presence has been continuous long enough to be a person sitting down.
    occupied_since: float | None = None
    empty_since: float | None = None
    seated_since: float | None = None
    served_at: float = 0.0
    # One waiter alert per seating. Without this a table left unattended re-alerts every
    # cooldown period forever, which is how staff learn to ignore the alerts entirely.
    table_alerted: bool = False


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

            # restaurant table: occupied, how long seated, and alert past the threshold
            if z.table:
                if st.occupancy > 0:
                    st.empty_since = None
                    if st.occupied_since is None:
                        st.occupied_since = ts
                    if st.seated_since is None and (ts - st.occupied_since) >= TABLE_SEATED_CONFIRM_SEC:
                        st.seated_since = st.occupied_since
                else:
                    if st.empty_since is None:
                        st.empty_since = ts
                    if (ts - st.empty_since) >= TABLE_FREE_CONFIRM_SEC:
                        st.occupied_since = None
                        st.seated_since = None
                        st.empty_since = None
                        st.table_alerted = False
                if st.seated_since is not None:
                    # Clock restarts whenever staff mark the table serviced.
                    anchor = max(st.seated_since, st.served_at)
                    if (ts - anchor) >= z.alert_after_sec and not st.table_alerted:
                        st.table_alerted = True
                        events.append({
                            "type": "table_waiting", "zone": z.name,
                            "note": f"{z.name} seated {int((ts - anchor) / 60)} min without being served",
                            "objects": ["person"],
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

    def serviced(self, zone_id: str) -> bool:
        """Mark a table served, restarting its wait clock. False if no such table."""
        for st in self.states:
            if st.zone.id == zone_id and st.zone.table:
                st.served_at = time.time()
                st.table_alerted = False
                return True
        return False

    def snapshot(self, now: float | None = None) -> list[dict[str, Any]]:
        ts = now if now is not None else time.time()
        out = []
        for st in self.states:
            z = st.zone
            row = {
                "id": z.id, "name": z.name, "occupancy": st.occupancy,
                "vehicle_count": st.vehicle_count,
                "parking": z.parking, "capacity": z.capacity,
                "source_id": z.source_id,
                "table": z.table, "seats": z.seats,
            }
            if z.table:
                anchor = max(st.seated_since, st.served_at) if st.seated_since is not None else None
                row["seated"] = st.seated_since is not None
                # Seconds the current party has been waiting since seating or last service.
                row["waiting_sec"] = int(ts - anchor) if anchor is not None else 0
                row["alert_after_sec"] = int(z.alert_after_sec)
                row["flagged"] = anchor is not None and (ts - anchor) >= z.alert_after_sec
            out.append(row)
        return out
