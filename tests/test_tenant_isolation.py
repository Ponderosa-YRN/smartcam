"""Route-level authorization tests.

Every assertion here corresponds to a bug that was actually present in this codebase. They
exist for one reason: without them, deleting a tenant check fails nothing, and the fixes are
one careless edit away from quietly returning.
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

SECRET = "test-secret-not-used-anywhere-real"


@pytest.fixture()
def world():
    db_path = tempfile.mktemp(suffix=".db")
    data_dir = Path(tempfile.mkdtemp())
    store = EventStore(db_path)
    try:
        t_a = store.create_tenant("alpha", "Alpha Hotel")
        t_b = store.create_tenant("beta", "Beta Estate")
        admin_a = store.create_user("admin_a", hash_password("x"), role="admin", tenant_id=t_a)
        viewer_a = store.create_user("viewer_a", hash_password("x"), role="viewer", tenant_id=t_a)
        admin_b = store.create_user("admin_b", hash_password("x"), role="admin", tenant_id=t_b)

        ev_a = store.add_event(
            {"camera_id": "cam-a", "camera_name": "A gate", "start_ts": 1000.0, "objects": ["person"]},
            tenant_id=t_a,
        )
        ev_b = store.add_event(
            {"camera_id": "cam-b", "camera_name": "B gate", "start_ts": 2000.0, "objects": ["person"]},
            tenant_id=t_b,
        )

        managers = SimpleNamespace(
            store=store,
            cfg=SimpleNamespace(
                sources=[
                    SimpleNamespace(id="cam-a", tenant_id=t_a),
                    SimpleNamespace(id="cam-b", tenant_id=t_b),
                ],
                data_dir=data_dir,
            ),
            pipelines={},
        )

        previous_manager = api_mod._manager
        previous_secret = api_mod._token_secret
        api_mod._manager = managers
        api_mod._token_secret = SECRET

        def token_for(user_id, role, tenant_id):
            return create_token(
                {"sub": user_id, "username": "u", "role": role, "tenant_id": tenant_id, "typ": "access"},
                SECRET,
            )

        yield SimpleNamespace(
            client=TestClient(api_mod.app),
            store=store,
            t_a=t_a,
            t_b=t_b,
            admin_a=admin_a,
            viewer_a=viewer_a,
            admin_b=admin_b,
            ev_a=ev_a,
            ev_b=ev_b,
            admin_a_token=token_for(admin_a, "admin", t_a),
            viewer_a_token=token_for(viewer_a, "viewer", t_a),
            admin_b_token=token_for(admin_b, "admin", t_b),
        )
    finally:
        api_mod._manager = previous_manager
        api_mod._token_secret = previous_secret
        store.close()
        if os.path.exists(db_path):
            os.remove(db_path)


def auth(token):
    return {"Authorization": "Bearer " + token}


# -- events and media ------------------------------------------------------

def test_event_list_returns_only_the_callers_tenant(world):
    r = world.client.get("/api/events", headers=auth(world.admin_a_token))
    assert r.status_code == 200
    assert [e["id"] for e in r.json()] == [world.ev_a]


def test_other_tenants_clip_is_indistinguishable_from_missing(world):
    r = world.client.get("/api/clips/" + str(world.ev_b), headers=auth(world.admin_a_token))
    assert r.status_code == 404


# -- camera control --------------------------------------------------------

def test_cannot_stop_a_camera_belonging_to_another_tenant(world):
    r = world.client.post("/api/stop/cam-b", headers=auth(world.admin_a_token))
    assert r.status_code == 404


def test_a_viewer_cannot_stop_a_camera(world):
    """Camera control is admin/manager only. The lowest role used to be able to stop recording."""
    r = world.client.post("/api/stop/cam-a", headers=auth(world.viewer_a_token))
    assert r.status_code == 403


# -- tenant routes ---------------------------------------------------------

def test_tenant_scoped_route_rejects_another_tenant(world):
    r = world.client.get("/tenants/" + str(world.t_b) + "/devices", headers=auth(world.admin_a_token))
    assert r.status_code == 404


def test_tenant_list_hides_other_customers(world):
    r = world.client.get("/tenants", headers=auth(world.admin_a_token))
    assert r.status_code == 200
    assert [t["slug"] for t in r.json()] == ["alpha"]


# -- users -----------------------------------------------------------------

def test_user_list_is_scoped_to_the_callers_tenant(world):
    r = world.client.get("/auth/users", headers=auth(world.admin_a_token))
    assert r.status_code == 200
    assert {u["username"] for u in r.json()} == {"admin_a", "viewer_a"}


def test_cannot_delete_a_user_from_another_tenant(world):
    r = world.client.delete("/auth/users/" + str(world.admin_b), headers=auth(world.admin_a_token))
    assert r.status_code == 404
    assert world.store.get_user(world.admin_b) is not None


# -- registration ----------------------------------------------------------

def test_public_registration_is_closed_by_default(world, monkeypatch):
    monkeypatch.delenv("SMART_CAM_ALLOW_SIGNUP", raising=False)
    r = world.client.post(
        "/auth/register",
        json={"company": "New Co", "username": "newbie", "password": "pw"},
    )
    assert r.status_code == 403
    assert world.store.get_user_by_username("newbie") is None


# -- tenant provisioning ---------------------------------------------------

def test_provisioning_creates_the_tenant_and_its_first_admin(world):
    """A tenant with no admin can never be signed into, so provisioning makes one."""
    r = world.client.post(
        "/tenants",
        headers=auth(world.admin_a_token),
        json={"slug": "gamma", "name": "Gamma Suites", "admin_username": "gamma_admin", "admin_password": "pw"},
    )
    assert r.status_code == 200
    body = r.json()
    admin = world.store.get_user_by_username("gamma_admin")
    assert admin is not None
    assert admin["tenant_id"] == body["id"]
    assert admin["role"] == "admin"


def test_provisioning_rejects_half_an_admin(world):
    r = world.client.post(
        "/tenants",
        headers=auth(world.admin_a_token),
        json={"slug": "delta", "admin_username": "delta_admin"},
    )
    assert r.status_code == 400


def test_provisioning_leaves_no_orphan_tenant_when_the_username_is_taken(world):
    """Validation runs before anything is written, so a rejection creates nothing."""
    r = world.client.post(
        "/tenants",
        headers=auth(world.admin_a_token),
        json={"slug": "epsilon", "admin_username": "admin_b", "admin_password": "pw"},
    )
    assert r.status_code == 409
    assert world.store.get_tenant_by_slug("epsilon") is None


# -- unauthenticated -------------------------------------------------------

def test_a_protected_route_needs_a_token(world):
    assert world.client.get("/api/events").status_code == 401
