"""The live stream URL, and who may ask for one.

An <img> tag cannot send an Authorization header, so the stream carries a short-lived
token in its query string. That token is minted by an authenticated call, which is where
the tenant check has to live - otherwise anyone with a guessed camera id could watch
another hotel.
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

SECRET = "stream-token-secret"


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
        managers = SimpleNamespace(
            store=store,
            pipelines={},
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
        )
    finally:
        api_mod._manager = previous_manager
        api_mod._token_secret = previous_secret
        store.close()
        if os.path.exists(db_path):
            os.remove(db_path)


def auth(token):
    return {"Authorization": "Bearer " + token}


def test_mints_a_url_for_your_own_camera(world):
    r = world.client.get("/api/stream-token/cam-a", headers=auth(world.admin_a))
    assert r.status_code == 200
    body = r.json()
    assert body["path"].startswith("/api/stream/cam-a?t=")
    assert body["expires_in"] > 0


def test_refuses_another_tenants_camera(world):
    r = world.client.get("/api/stream-token/cam-b", headers=auth(world.admin_a))
    assert r.status_code == 404


def test_refuses_an_unknown_camera(world):
    r = world.client.get("/api/stream-token/nope", headers=auth(world.admin_a))
    assert r.status_code == 404


def test_needs_a_token(world):
    r = world.client.get("/api/stream-token/cam-a")
    assert r.status_code in (401, 403)


def bare_request(query: str):
    """A request like the one an <img> tag makes: no Authorization header."""
    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/stream/cam-a",
        "headers": [],
        "query_string": query.encode(),
    }
    return Request(scope)


def mint_query(world, source_id: str) -> str:
    r = world.client.get("/api/stream-token/" + source_id, headers=auth(world.admin_a))
    assert r.status_code == 200
    return r.json()["path"].split("?t=", 1)[1]


def test_a_query_token_authorises_a_request_with_no_header(world):
    """The bug this covers: the middleware used to 401 the <img> request first."""
    tok = mint_query(world, "cam-a")
    assert api_mod._stream_authorised(bare_request("t=" + tok), "cam-a") is True


def test_a_query_token_is_scoped_to_its_own_camera(world):
    tok = mint_query(world, "cam-a")
    assert api_mod._stream_authorised(bare_request("t=" + tok), "cam-b") is False


def test_no_token_means_no_stream(world):
    assert api_mod._stream_authorised(bare_request(""), "cam-a") is False


def test_a_garbage_token_means_no_stream(world):
    assert api_mod._stream_authorised(bare_request("t=not-a-real-token"), "cam-a") is False

