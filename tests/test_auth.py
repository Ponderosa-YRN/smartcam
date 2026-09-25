"""Dependency-free auth tests (password hashing, tokens, user store)."""
import os
import tempfile

from smartcam.auth import authenticate_user, bootstrap_admin
from smartcam.db import EventStore
from smartcam.security import (
    create_token,
    hash_password,
    load_or_create_secret,
    new_secret,
    read_token,
    verify_password,
)


def test_password_hash_roundtrip():
    h = hash_password("s3cret")
    assert h.startswith("scrypt$")
    assert verify_password("s3cret", h)
    assert not verify_password("wrong", h)
    assert not verify_password("x", "not-a-hash")


def test_token_roundtrip():
    secret = new_secret()
    tok = create_token({"sub": 1, "role": "admin", "typ": "access"}, secret)
    assert read_token(tok, secret, 3600) == {"sub": 1, "role": "admin", "typ": "access"}
    assert read_token(tok, "other-secret", 3600) is None
    assert read_token(tok + "x", secret, 3600) is None
    assert read_token(tok, secret, 0) is None


def test_load_or_create_secret():
    d = tempfile.mkdtemp()
    path = os.path.join(d, ".secret")
    os.environ["SMART_CAM_TOKEN_SECRET"] = "env-secret"
    try:
        assert load_or_create_secret(path) == "env-secret"
    finally:
        os.environ.pop("SMART_CAM_TOKEN_SECRET", None)
    s1 = load_or_create_secret(path)
    assert s1 and s1 != "env-secret"
    assert load_or_create_secret(path) == s1  # persisted across calls
    os.remove(path)
    os.rmdir(d)


def test_user_store_crud():
    p = tempfile.mktemp(suffix=".db")
    s = EventStore(p)
    try:
        assert s.count_users() == 0
        uid = s.create_user("alice", hash_password("pw1"), role="admin")
        assert s.count_users() == 1
        assert s.get_user_by_username("alice")["role"] == "admin"
        s.update_user(uid, role="viewer")
        assert s.get_user(uid)["role"] == "viewer"
        assert [u["username"] for u in s.list_users()] == ["alice"]
        s.delete_user(uid)
        assert s.count_users() == 0
    finally:
        s.close()
        os.remove(p)


def test_authenticate_user():
    p = tempfile.mktemp(suffix=".db")
    s = EventStore(p)
    try:
        s.create_user("bob", hash_password("hunter2"), role="security")
        u = authenticate_user(s, "bob", "hunter2")
        assert u is not None and u["role"] == "security"
        assert authenticate_user(s, "bob", "bad") is None
        assert authenticate_user(s, "nobody", "x") is None
    finally:
        s.close()
        os.remove(p)


def test_bootstrap_admin():
    p = tempfile.mktemp(suffix=".db")
    s = EventStore(p)
    try:
        assert bootstrap_admin(None) is False
        os.environ["SMART_CAM_ADMIN_PASSWORD"] = "boot-pass"
        try:
            assert bootstrap_admin(s) is True
            assert s.get_user_by_username("admin")["role"] == "admin"
            assert bootstrap_admin(s) is False  # already has a user
        finally:
            os.environ.pop("SMART_CAM_ADMIN_PASSWORD", None)
    finally:
        s.close()
        os.remove(p)


def test_tenants_sites_devices():
    p = tempfile.mktemp(suffix=".db")
    s = EventStore(p)
    try:
        assert s.schema_version() == 12
        tid = s.ensure_default_tenant()
        assert s.count_tenants() == 1 and tid == 1
        t2 = s.create_tenant("hotel-a", "Hotel A")
        assert s.get_tenant_by_slug("hotel-a")["name"] == "Hotel A"
        assert len(s.list_tenants()) == 2
        sid = s.create_site(t2, "Lobby")
        did = s.create_device(t2, "Edge Box", site_id=sid)
        assert s.list_sites(t2)[0]["name"] == "Lobby"
        assert s.list_devices(t2)[0]["name"] == "Edge Box"
        # users get tenant_id + legacy backfill
        s.create_user("alice", "h", role="admin", tenant_id=t2)
        s.create_user("legacy", "h2", role="viewer")
        s.ensure_default_tenant()
        assert s.get_user_by_username("alice")["tenant_id"] == t2
        assert s.get_user_by_username("legacy")["tenant_id"] == tid
        assert [u["username"] for u in s.list_users(t2)] == ["alice"]
    finally:
        s.close()
        os.remove(p)


def test_tenant_scoping():
    p = tempfile.mktemp(suffix=".db")
    s = EventStore(p)
    try:
        assert s.local_tenant_id == 1
        eid = s.add_event({"camera_id": "c1", "camera_name": "Cam", "start_ts": 1000.0, "objects": ["person"]})
        assert s.get_event(eid)["tenant_id"] == 1
        t2 = s.create_tenant("hotel-b", "Hotel B")
        eid2 = s.add_event({"camera_id": "c1", "camera_name": "Cam", "start_ts": 2000.0, "objects": ["car"]}, tenant_id=t2)
        assert len(s.list_events(tenant_id=1)) == 1
        assert len(s.list_events(tenant_id=t2)) == 1
        assert len(s.list_events()) == 2
        assert s.count_events(tenant_id=1) == 1
        assert s.count_events(tenant_id=t2) == 1
        assert s.list_open_alerts(tenant_id=1)[0]["id"] == eid
        assert len(s.search(["person"], tenant_id=t2)) == 0
        assert len(s.search(["car"], tenant_id=t2)) == 1
    finally:
        s.close()
        os.remove(p)


def test_invites():
    p = tempfile.mktemp(suffix=".db")
    s = EventStore(p)
    try:
        t = s.ensure_default_tenant()
        iid = s.create_invite(t, "a@b.com", "viewer", "tok", 9999999999.0)
        assert s.get_invite_by_token("tok")["email"] == "a@b.com"
        assert len(s.list_invites(t)) == 1
        s.consume_invite(iid)
        assert s.get_invite_by_token("tok")["consumed"] == 1
        s.delete_invite(iid)
        assert s.list_invites(t) == []
    finally:
        s.close()
        os.remove(p)
