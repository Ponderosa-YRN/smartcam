"""Restaurant table tracking.

The logic that matters is hysteresis: a waiter walking past must not turn a table red, and a
single dropped frame must not turn a seated table green. Both are tested here because both
are the difference between a floor map staff trust and one they ignore.
"""
from smartcam.config import ZoneConfig
from smartcam.detector import Detection
from smartcam.zones import ZoneTracker

FRAME = (1000, 1000)
TABLE = [[0.2, 0.4], [0.8, 0.4], [0.8, 0.95], [0.2, 0.95]]


def seated(track_id: int = 7) -> Detection:
    # feet point ~(0.5, 0.9) -> inside the polygon
    return Detection(xyxy=[450, 500, 550, 900], cls=0, label="person", conf=0.9, track_id=track_id)


def make_tracker(**overrides):
    zone = ZoneConfig(
        id="table-1",
        name="Table 12",
        source_id="cam-1",
        points=TABLE,
        classes=["person"],
        table=True,
        seats=4,
        alert_after_sec=overrides.pop("alert_after_sec", 600.0),
        **overrides,
    )
    return ZoneTracker([zone], cooldown=0.0)


def run(tracker, t0, t1, dets, step=1.0):
    """Feed frames from t0 to t1; return every event raised."""
    events = []
    t = t0
    while t <= t1:
        events.extend(tracker.update(dets, t, *FRAME))
        t += step
    return events


def row(tracker, now):
    return tracker.snapshot(now)[0]


def test_a_table_starts_free():
    tracker = make_tracker()
    run(tracker, 0, 5, [])
    r = row(tracker, 5)
    assert r["table"] is True
    assert r["seated"] is False
    assert r["waiting_sec"] == 0
    assert r["flagged"] is False


def test_a_waiter_walking_past_does_not_seat_the_table():
    """Presence shorter than the confirm window must not turn the table red."""
    tracker = make_tracker()
    run(tracker, 0, 5, [seated()])       # 5 s only
    assert row(tracker, 5)["seated"] is False


def test_sustained_presence_seats_the_table_and_counts_waiting_time():
    tracker = make_tracker()
    run(tracker, 0, 60, [seated()])
    r = row(tracker, 60)
    assert r["seated"] is True
    # Waiting is measured from arrival, not from the confirmation moment.
    assert 55 <= r["waiting_sec"] <= 61


def test_a_dropped_frame_does_not_free_an_occupied_table():
    tracker = make_tracker()
    run(tracker, 0, 60, [seated()])
    run(tracker, 61, 75, [])              # 15 s of no detections, under the free window
    assert row(tracker, 75)["seated"] is True


def test_a_genuinely_empty_table_frees_again():
    tracker = make_tracker()
    run(tracker, 0, 60, [seated()])
    run(tracker, 61, 120, [])             # empty well past the free window
    r = row(tracker, 120)
    assert r["seated"] is False
    assert r["waiting_sec"] == 0


def test_alert_fires_once_past_the_threshold():
    tracker = make_tracker(alert_after_sec=60.0)
    events = run(tracker, 0, 200, [seated()])
    table_events = [e for e in events if e["type"] == "table_waiting"]
    assert len(table_events) == 1
    assert "Table 12" in table_events[0]["note"]
    assert row(tracker, 200)["flagged"] is True


def test_no_alert_before_the_threshold():
    tracker = make_tracker(alert_after_sec=600.0)
    events = run(tracker, 0, 300, [seated()])
    assert [e for e in events if e["type"] == "table_waiting"] == []


def test_marking_serviced_restarts_the_wait_clock():
    tracker = make_tracker(alert_after_sec=60.0)
    run(tracker, 0, 120, [seated()])
    assert row(tracker, 120)["flagged"] is True

    assert tracker.serviced("table-1") is True
    r = row(tracker, 130)
    assert r["flagged"] is False
    assert r["waiting_sec"] <= 10
    assert r["seated"] is True


def test_a_new_party_alerts_again_after_the_table_frees():
    """The once-per-seating rule must reset, or a second guest is never flagged."""
    tracker = make_tracker(alert_after_sec=60.0)
    run(tracker, 0, 120, [seated()])
    run(tracker, 121, 200, [])            # table empties and frees
    events = run(tracker, 201, 400, [seated()])   # a new party sits down
    assert len([e for e in events if e["type"] == "table_waiting"]) == 1


def test_serviced_ignores_a_zone_that_is_not_a_table():
    tracker = ZoneTracker([ZoneConfig(id="z", name="Gate", points=TABLE)], cooldown=0.0)
    assert tracker.serviced("z") is False
    assert tracker.serviced("nope") is False
