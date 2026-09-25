"""Billing stub + usage metering tests."""

import os
import tempfile

from smartcam.billing import PLANS, plan_limits
from smartcam.db import EventStore


def test_plan_limits():
    assert plan_limits("free")["max_cameras"] == 2
    assert plan_limits("free")["max_storage_gb"] == 5
    assert plan_limits("pro")["max_cameras"] == 25
    assert plan_limits("pro")["max_storage_gb"] == 100
    assert plan_limits("enterprise")["max_cameras"] == -1
    assert plan_limits("enterprise")["max_storage_gb"] == -1
    assert plan_limits("bogus")["label"] == "Free"  # unknown plan falls back to free
    assert set(PLANS) == {"free", "pro", "enterprise"}


def test_tenant_billing_columns():
    p = tempfile.mktemp(suffix=".db")
    s = EventStore(p)
    try:
        tid = s.create_tenant("billing-hotel", "Billing Hotel", plan="pro")
        t = s.get_tenant(tid)
        assert t["plan"] == "pro"
        assert t["billing_status"] == "active"
        assert t["stripe_customer_id"] == ""
        s.update_tenant(
            tid,
            plan="enterprise",
            billing_status="past_due",
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_456",
        )
        t2 = s.get_tenant(tid)
        assert t2["plan"] == "enterprise"
        assert t2["billing_status"] == "past_due"
        assert t2["stripe_customer_id"] == "cus_123"
        assert t2["stripe_subscription_id"] == "sub_456"
        # 'name' is an allowed field; unknown fields are ignored
        s.update_tenant(tid, name="Renamed", not_a_field="x")
        t3 = s.get_tenant(tid)
        assert t3["name"] == "Renamed"
        assert "not_a_field" not in t3
    finally:
        s.close()
        os.remove(p)
