"""The events list can be asked for without the AI summary.

The dashboard polls this endpoint with limit=200 every five seconds and renders eight rows of
four fields. The summaries are several hundred characters each, so sending them there is
bandwidth for text nobody reads - but the Events page does read them, so the field has to
stay available by default.
"""
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from smartcam import api as api_mod
from smartcam.db import EventStore
from smartcam.security import create_token, hash_password

SECRET = "events-slim-secret"


@pytest.fixture()
def world():
    db_path = tempfile.mktemp(suffix=".db")
    data_dir = Path(tempfile.mkdtemp())
    os.environ["SMART_CAM_CONFIG"] = str(data_dir / "config.json")
    store = EventStore(db_path)
    try:
        tenant = store.create_tenant("alpha", "Alpha Hotel")
        admin = store.create_user("admin_a", hash_password("x"), role="admin", tenant_id=tenant)
        event_id = store.add_event(
            {
                "camera_id": "cam-a",
                "camera_name": "Camera 07",
                "start_ts": 1000.0,
                "event_type": "detection",
                "top_object": "person",
            },
            tenant_id=tenant,
        )
        # add_event does not take the summary; it is written by the summariser afterwards.
        store.update_event(
            event_id,
            summary="A single person is visible, seated at a desk, in a well-lit room.",
            summary_model="test",
        )
        previous_manager = api_mod._manager
        previous_secret = api_mod._token_secret
        api_mod._manager = SimpleNamespace(
            store=store,
            pipelines={},
            cfg=SimpleNamespace(sources=[], data_dir=data_dir, zones=[]),
        )
        api_mod._token_secret = SECRET
        token = create_token(
            {"sub": admin, "username": "admin_a", "role": "admin", "tenant_id": tenant, "typ": "access"},
            SECRET,
        )
        yield TestClient(api_mod.app, raise_server_exceptions=False), token, tenant
    finally:
        api_mod._manager = previous_manager
        api_mod._token_secret = previous_secret
        store.close()
        if os.path.exists(db_path):
            os.remove(db_path)


def auth(token):
    return {"Authorization": "Bearer " + token}


def test_the_summary_is_sent_by_default(world):
    client, token, _ = world
    rows = client.get("/api/events?limit=10", headers=auth(token)).json()
    assert len(rows) == 1
    assert rows[0]["summary"].startswith("A single person")


def test_slim_omits_the_summary_but_keeps_the_row(world):
    client, token, _ = world
    rows = client.get("/api/events?limit=10&slim=true", headers=auth(token)).json()
    assert len(rows) == 1, "the dashboard counts these rows, so slim must not drop them"
    assert "summary" not in rows[0]
    assert "summary_model" not in rows[0]
    assert rows[0]["event_type"] == "detection"
    assert rows[0]["top_object"] == "person"
