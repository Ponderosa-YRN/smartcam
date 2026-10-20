"""Full-surface API test: every route, with and without a token.

The assertion is deliberately weak - "not a 500" - because most routes legitimately
return 404 for a resource that does not exist. What this catches is the class of bug that
is invisible in normal use: a route that raises on an edge case, a dependency that is
imported but missing, a handler nobody has called since it was written.
"""
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

SECRET = "surface-test-secret"


@pytest.fixture(scope="module")
def world():
    db_path = tempfile.mktemp(suffix=".db")
    data_dir = Path(tempfile.mkdtemp())
    config_path = data_dir / "config.json"
    os.environ["SMART_CAM_CONFIG"] = str(config_path)
    os.environ.pop("SMART_CAM_ALLOW_SIGNUP", None)
    os.environ.pop("SMART_CAM_PLATFORM_KEY", None)

    from smartcam import api as api_mod
    from smartcam.db import EventStore
    from smartcam.security import create_token, hash_password

    store = EventStore(db_path)
    tenant = store.create_tenant("surface", "Surface Ltd")
    admin_id = store.create_user("surface_admin", hash_password("x"), role="admin", tenant_id=tenant)
    viewer_id = store.create_user("surface_viewer", hash_password("x"), role="viewer", tenant_id=tenant)
    event_id = store.add_event(
        {"camera_id": "cam-a", "camera_name": "Gate", "start_ts": 1000.0, "objects": ["person"]},
        tenant_id=tenant,
    )

    class FakePipeline:
        running = True
        latest_frame = None
        stats = {"status": "running"}

        def health(self):
            return "ok"

    class FakeManager:
        def __init__(self):
            self.store = store
            self.pipelines = {"cam-a": FakePipeline()}
            self.cfg = SimpleNamespace(
                sources=[SimpleNamespace(id="cam-a", name="Gate", tenant_id=tenant)],
                data_dir=data_dir,
                clips_dir=data_dir / "clips",
                thumbs_dir=data_dir / "thumbs",
                webrtc=SimpleNamespace(enabled=False),
            )

        def start(self, source_id):
            return True

        def stop(self, source_id):
            return True

        def add_source(self, src):
            self.cfg.sources.append(src)
            return src.id

        def remove_source(self, source_id):
            self.cfg.sources = [s for s in self.cfg.sources if s.id != source_id]

        def remove_source_by_id(self, source_id):
            self.remove_source(source_id)

    previous_manager = api_mod._manager
    previous_secret = api_mod._token_secret
    api_mod._manager = FakeManager()
    api_mod._token_secret = SECRET

    def token(uid, role):
        return create_token({"sub": uid, "username": "u", "role": role, "tenant_id": tenant, "typ": "access"}, SECRET)

    yield SimpleNamespace(
        client=TestClient(api_mod.app, raise_server_exceptions=False),
        routes=[r for r in api_mod.app.routes if hasattr(r, "methods")],
        admin=token(admin_id, "admin"),
        viewer=token(viewer_id, "viewer"),
        event_id=event_id,
        tenant=tenant,
        store=store,
    )

    api_mod._manager = previous_manager
    api_mod._token_secret = previous_secret
    store.close()
    if os.path.exists(db_path):
        os.remove(db_path)


PUBLIC = {"/api/health", "/auth/login", "/auth/refresh", "/auth/register", "/openapi.json", "/docs", "/redoc",
          "/docs/oauth2-redirect"}

# Endpoints that would rewrite real state on disk if called with made-up values.
SKIP = {"/api/config", "/docs", "/openapi.json", "/redoc", "/docs/oauth2-redirect"}


def _fill(path, world):
    return (path.replace("{source_id}", "cam-a")
                .replace("{event_id}", str(world.event_id))
                .replace("{tenant_id}", str(world.tenant))
                .replace("{user_id}", "1")
                .replace("{device_id}", "1")
                .replace("{identity_id}", "1")
                .replace("{invite_id}", "1")
                .replace("{face_id}", "1")
                .replace("{token}", "nope")
                .replace("{slug}", "s"))


def test_no_route_raises_with_a_valid_token(world):
    failures = []
    for route in world.routes:
        if route.path in SKIP:
            continue
        url = _fill(route.path, world)
        for method in sorted(route.methods):
            if method in ("HEAD", "OPTIONS"):
                continue
            try:
                res = world.client.request(
                    method, url,
                    headers={"Authorization": "Bearer " + world.admin},
                    json={} if method in ("POST", "PUT", "PATCH") else None,
                )
            except Exception as exc:  # transport-level blow up
                failures.append((method, url, "EXC " + type(exc).__name__ + ": " + str(exc)[:120]))
                continue
            if res.status_code >= 500:
                failures.append((method, url, res.status_code))
    assert not failures, "routes returned 5xx: " + repr(failures)


def test_every_non_public_route_refuses_an_anonymous_caller(world):
    leaks = []
    for route in world.routes:
        if route.path in SKIP or route.path in PUBLIC or route.path.startswith("/invites/"):
            continue
        url = _fill(route.path, world)
        for method in sorted(route.methods):
            if method in ("HEAD", "OPTIONS"):
                continue
            res = world.client.request(method, url, json={} if method in ("POST", "PUT", "PATCH") else None)
            if res.status_code not in (401, 403):
                leaks.append((method, url, res.status_code))
    assert not leaks, "reachable without a token: " + repr(leaks)


def test_every_non_public_route_refuses_a_viewer_who_should_not_write(world):
    """Reads are fine for a viewer; anything that changes state must not be."""
    leaks = []
    write_methods = {"POST", "PUT", "PATCH", "DELETE"}
    read_only = {"/api/events", "/api/plates", "/api/faces", "/api/face_matches", "/api/identities",
                 "/api/config", "/api/sources", "/api/class_names", "/api/health"}
    for route in world.routes:
        if route.path in SKIP or route.path in PUBLIC:
            continue
        url = _fill(route.path, world)
        for method in sorted(route.methods):
            if method not in write_methods:
                continue
            if any(route.path.startswith(p + "/") or route.path == p for p in read_only):
                continue
            # Logout is a deliberate no-op: tokens are stateless and revocation happens by
            # re-reading the user row, so there is nothing server-side to end.
            if route.path == "/auth/logout":
                continue
            res = world.client.post(url, headers={"Authorization": "Bearer " + world.viewer}, json={})
            if res.status_code < 400:
                leaks.append((method, url, res.status_code))
    assert not leaks, "a viewer could write: " + repr(leaks)
