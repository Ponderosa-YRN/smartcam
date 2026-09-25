"""Plans and usage metering (billing stub).

This is the data model + metering for billing. Actual Stripe payments
(creating customers/subscriptions, webhooks, invoicing) are a follow-up that
requires Stripe keys; tenants already carry stripe_customer_id /
stripe_subscription_id fields for when that integration lands.
"""
from __future__ import annotations

from pathlib import Path

# plan -> limits. -1 means unlimited.
PLANS = {
    "free": {"label": "Free", "max_cameras": 2, "max_storage_gb": 5},
    "pro": {"label": "Pro", "max_cameras": 25, "max_storage_gb": 100},
    "enterprise": {"label": "Enterprise", "max_cameras": -1, "max_storage_gb": -1},
}


def plan_limits(plan: str) -> dict:
    return PLANS.get(plan, PLANS["free"])


def _dir_size(path) -> int:
    p = Path(path)
    if not p.exists():
        return 0
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def tenant_usage(cfg, store, tenant_id: int) -> dict:
    """Report a tenant's current usage (cameras, events, plates, storage)."""
    cameras = len([s for s in cfg.sources if s.enabled])
    events = store.count_events(tenant_id=tenant_id)
    plates = len(store.list_plates(tenant_id=tenant_id, limit=100000))
    faces = len(store.list_faces(tenant_id=tenant_id))
    identities = len(store.list_identities(tenant_id=tenant_id))
    storage_bytes = _dir_size(cfg.clips_dir) + _dir_size(cfg.thumbs_dir)
    return {
        "cameras": cameras,
        "events": events,
        "plates": plates,
        "faces": faces,
        "identities": identities,
        "storage_bytes": storage_bytes,
    }
