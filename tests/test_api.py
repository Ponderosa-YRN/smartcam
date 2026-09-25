"""Test the FastAPI backend via TestClient."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["SMART_CAM_CONFIG"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config_phase2.json")

from fastapi.testclient import TestClient

from smartcam.api import app

with TestClient(app) as client:
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    print("health OK:", r.json())

    r = client.get("/api/sources")
    assert r.status_code == 200 and len(r.json()) == 1
    print("sources OK:", r.json())

    r = client.get("/api/events")
    assert r.status_code == 200
    print("events OK (count:", len(r.json()), ")")

    r = client.get("/api/identities")
    assert r.status_code == 200
    print("identities OK:", r.json())

    r = client.post("/api/start/demo")
    assert r.status_code == 200
    print("start OK:", r.json())

    r = client.get("/api/status/demo")
    assert r.status_code == 200 and r.json()["status"] in ("running", "stopped")
    print("status OK")

    r = client.post("/api/stop/demo")
    assert r.status_code == 200
    print("stop OK:", r.json())

    r = client.get("/api/unknown")
    assert r.status_code == 404
    print("404 OK")

print("API TEST PASSED")
