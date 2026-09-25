"""Edge ingestion: device attribution + incremental sync reads."""

import os
import tempfile

from smartcam.db import EventStore


def test_add_event_device_attribution():
    p = tempfile.mktemp(suffix=".db")
    s = EventStore(p)
    try:
        assert s.schema_version() == 12
        tid = s.ensure_default_tenant()
        t2 = s.create_tenant("edge-hotel", "Edge Hotel")
        eid = s.add_event(
            {"camera_id": "c1", "camera_name": "Cam", "start_ts": 1000.0, "objects": ["person"]},
            tenant_id=t2, device_id=7,
        )
        ev = s.get_event(eid)
        assert ev["tenant_id"] == t2
        assert ev["device_id"] == 7
        # local (non-ingested) writes still fall back to the default tenant
        eid2 = s.add_event({"camera_id": "c1", "start_ts": 2000.0, "objects": ["car"]})
        assert s.get_event(eid2)["tenant_id"] == tid
        assert s.get_event(eid2)["device_id"] is None
    finally:
        s.close()
        os.remove(p)


def test_occupancy_device_attribution():
    p = tempfile.mktemp(suffix=".db")
    s = EventStore(p)
    try:
        oid = s.add_occupancy_sample(1000.0, 3, 1, tenant_id=9, device_id=5)
        o = s.list_occupancy_samples(tenant_id=9)[0]
        assert o["id"] == oid
        assert o["tenant_id"] == 9
        assert o["device_id"] == 5
    finally:
        s.close()
        os.remove(p)


def test_since_id_incremental_reads():
    p = tempfile.mktemp(suffix=".db")
    s = EventStore(p)
    try:
        for i in range(3):
            s.add_event({"camera_id": "c1", "start_ts": float(i), "objects": ["person"]})
        assert [e["id"] for e in s.list_events_since_id(0)] == [1, 2, 3]
        assert [e["id"] for e in s.list_events_since_id(1)] == [2, 3]
        assert s.list_events_since_id(3) == []

        for i in range(2):
            s.add_occupancy_sample(float(i), i, 0)
        assert [o["id"] for o in s.list_occupancy_since_id(0)] == [1, 2]
        assert [o["id"] for o in s.list_occupancy_since_id(1)] == [2]
        assert s.list_occupancy_since_id(2) == []
    finally:
        s.close()
        os.remove(p)
