"""The table endpoints, not just the state machine.

The tracker tests cover hysteresis. These cover the HTTP route, because a tenant check that
is only proved at the state-machine level does not stop the route from skipping it - which
is exactly how the serviced endpoint shipped without one.
"""
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from smartcam import api as api_mod
from smartcam.config import ZoneConfig
from smartcam.db import EventStore
from smartcam.security import create_token, hash_password
from smartcam.zones import ZoneTracker

SECRET = "table-api-secret"
TABLE_SHAPE = [[0.2, 0.4], [0.8, 0.4], [0.8, 0.95], [0.2, 0.95]]


@pytest.fixture()
def world():
    db_path = tempfile.mktemp(suffix=".db")
    data_dir = Path(tempfile.mkdtemp())
    os.environ["SMART_CAM_CONFIG"] = str(data_dir / "config.json")
    store = EventStore(db_path)
    try:
        t_a = store.create_tenant("alpha", "Alpha Hotel")
        t_b = store.create_tenant("beta", "Beta Estate")
        admin_a = store.create_user("admin_a", hash_password("x"), role="admin", tenant_id=t_a)
        admin_b = store.create_user("admin_b", hash_password("x"), role="admin", tenant_id=t_b)
        # A real row: the middleware re-reads the user on every request, so a token naming a
        # non-existent user is a 401 before any role check is reached.
        viewer_a = store.create_user("viewer_a", hash_password("x"), role="viewer", tenant_id=t_a)

        def tracker(zone_id: str, source: str) -> ZoneTracker:
            zone = ZoneConfig(
                id=zone_id, name=zone_id, source_id=source, points=TABLE_SHAPE,
                classes=["person"], table=True, seats=4, alert_after_sec=600.0,
            )
            return ZoneTracker([zone], cooldown=0.0)

        pipelines = {
            "cam-a": SimpleNamespace(zones=tracker("table-a", "cam-a")),
            "cam-b": SimpleNamespace(zones=tracker("table-b", "cam-b")),
        }
        managers = SimpleNamespace(
            store=store,
            pipelines=pipelines,
            cfg=SimpleNamespace(
                sources=[
                    SimpleNamespace(id="cam-a", tenant_id=t_a),
                    SimpleNamespace(id="cam-b", tenant_id=t_b),
                ],
                data_dir=data_dir,
                zones=[],
            ),
        )

        previous_manager = api_mod._manager
        previous_secret = api_mod._token_secret
        api_mod._manager = managers
        api_mod._token_secret = SECRET

        def token(uid, tenant, role="admin"):
            return create_token(
                {"sub": uid, "username": "u", "role": role, "tenant_id": tenant, "typ": "access"}, SECRET
            )

        yield SimpleNamespace(
            client=TestClient(api_mod.app, raise_server_exceptions=False),
            admin_a=token(admin_a, t_a),
            admin_b=token(admin_b, t_b),
            viewer_a=token(viewer_a, t_a, role="viewer"),
            trackers=pipelines,
        )
    finally:
        api_mod._manager = previous_manager
        api_mod._token_secret = previous_secret
        store.close()
        if os.path.exists(db_path):
            os.remove(db_path)


def auth(token):
    return {"Authorization": "Bearer " + token}


def test_tables_list_shows_only_the_callers_cameras(world):
    r = world.client.get("/api/tables", headers=auth(world.admin_a))
    assert r.status_code == 200
    assert [t["id"] for t in r.json()] == ["table-a"]


def test_servicing_your_own_table_works(world):
    r = world.client.post("/api/tables/table-a/serviced", headers=auth(world.admin_a))
    assert r.status_code == 200


def test_servicing_another_tenants_table_is_a_404(world):
    """The bug this test exists for: the route used to skip the tenant check entirely."""
    r = world.client.post("/api/tables/table-b/serviced", headers=auth(world.admin_a))
    assert r.status_code == 404


def test_servicing_an_unknown_table_is_a_404(world):
    r = world.client.post("/api/tables/nope/serviced", headers=auth(world.admin_a))
    assert r.status_code == 404


def test_a_viewer_cannot_service_a_table(world):
    r = world.client.post("/api/tables/table-a/serviced", headers=auth(world.viewer_a))
    assert r.status_code == 403
