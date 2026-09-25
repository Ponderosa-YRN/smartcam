"""Per-tenant secrets and edge-device credentials (stub).

Two pieces of the multi-tenant security model:

1. Per-tenant signing secrets. Each tenant's bearer tokens are signed with a
   key derived from the master secret via HMAC-SHA256, so a compromise of one
   tenant's key does not expose any other tenant's tokens and no per-tenant
   material is stored at rest. derive_tenant_secret() is the single seam to
   swap for Vault/KMS in production (read the key from Vault, cache it, rotate
   on a schedule) without changing any caller.

2. Edge-device tokens. A device token is an opaque 'scd_<tenant>.<signed>'
   string: the prefix carries the tenant id so we know which derived secret to
   verify with, and the signed body carries the device id + a generation
   counter. Rotation bumps the generation (invalidating older tokens), and
   deleting the device row revokes it entirely.
"""
from __future__ import annotations

import hashlib
import hmac

from .security import create_token, read_token

# Device credentials are long-lived by design (edge boxes must survive network
# partitions) but are revocable via rotation or device deletion.
DEVICE_TOKEN_MAX_AGE = 365 * 24 * 3600

_TOKEN_PREFIX = "scd_"


def derive_tenant_secret(master_secret: str, tenant_id: int) -> str:
    """Derive a tenant's signing key from the master secret (Vault/KMS seam)."""
    return hmac.new(
        master_secret.encode("utf-8"),
        ("tenant:%d" % tenant_id).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def issue_device_token(master_secret: str, tenant_id: int, device_id: int, generation: int) -> str:
    """Issue a signed device credential for device_id in tenant_id."""
    secret = derive_tenant_secret(master_secret, tenant_id)
    signed = create_token({"device_id": device_id, "gen": generation, "typ": "device"}, secret)
    return _TOKEN_PREFIX + "%d.%s" % (tenant_id, signed)


def parse_device_token(master_secret: str, token: str) -> dict | None:
    """Validate a device token; return {tenant_id, device_id, gen} or None."""
    if not token or not token.startswith(_TOKEN_PREFIX):
        return None
    rest = token[len(_TOKEN_PREFIX):]
    tenant_part, _, signed = rest.partition(".")
    if not signed:
        return None
    try:
        tenant_id = int(tenant_part)
    except ValueError:
        return None
    payload = read_token(signed, derive_tenant_secret(master_secret, tenant_id), DEVICE_TOKEN_MAX_AGE)
    if payload is None or payload.get("typ") != "device":
        return None
    device_id = payload.get("device_id")
    gen = payload.get("gen")
    if not isinstance(device_id, int) or not isinstance(gen, int):
        return None
    return {"tenant_id": tenant_id, "device_id": device_id, "gen": gen}
