"""Per-tenant secrets and edge-device token tests."""

import os
import tempfile

from smartcam.db import EventStore
from smartcam.secrets import (
    derive_tenant_secret,
    issue_device_token,
    parse_device_token,
)


def test_derive_tenant_secret_is_stable_and_distinct():
    s1 = derive_tenant_secret("master", 1)
    assert s1 == derive_tenant_secret("master", 1)
    assert s1 != derive_tenant_secret("master", 2)
    assert s1 != derive_tenant_secret("other", 1)


def test_device_token_roundtrip_and_generation():
    master = "master-secret"
    tok = issue_device_token(master, 7, 42, 0)
    assert tok.startswith("scd_7.")
    assert parse_device_token(master, tok) == {"tenant_id": 7, "device_id": 42, "gen": 0}
    # wrong tenant prefix (signed under a different tenant key) -> rejected
    signed = tok.split(".", 1)[1]
    assert parse_device_token(master, "scd_8." + signed) is None
    # wrong master secret -> rejected
    assert parse_device_token("wrong", tok) is None
    # malformed / empty -> rejected
    assert parse_device_token(master, "not-a-token") is None
    assert parse_device_token(master, "") is None
    assert parse_device_token(master, "scd_7") is None
    # rotated generation yields a different token and claims
    tok2 = issue_device_token(master, 7, 42, 1)
    assert tok2 != tok
    assert parse_device_token(master, tok2)["gen"] == 1


def test_device_generation_and_lifecycle():
    p = tempfile.mktemp(suffix=".db")
    s = EventStore(p)
    try:
        assert s.schema_version() == 12
        did = s.create_device(1, "Edge Box")
        assert s.get_device(did)["token_generation"] == 0
        assert s.bump_device_token_generation(did) == 1
        assert s.get_device(did)["token_generation"] == 1
        assert s.get_device(did)["last_seen"] is None
        s.touch_device(did)
        assert s.get_device(did)["last_seen"] is not None
        s.delete_device(did)
        assert s.get_device(did) is None
    finally:
        s.close()
        os.remove(p)
