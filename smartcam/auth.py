"""Authentication: legacy config-file check + DB-backed user authentication."""
from __future__ import annotations

from typing import Any

from .config import AuthConfig, hash_password as _config_hash
from .security import hash_password, verify_password

# Roles (keep in sync with the AuthUser.role docstring in config.py).
ROLES = ("admin", "security", "manager", "viewer")


def authenticate(cfg: AuthConfig, username: str, password: str) -> str | None:
    """Legacy config-file authentication (used before/without a user store).

    Returns the role, or None if invalid. Auth disabled => full access ("admin").
    """
    if not cfg.enabled:
        return "admin"
    h = _config_hash(password)
    for u in cfg.users:
        if u.username == username and u.password_hash == h:
            return u.role
    return None


def authenticate_user(store: Any, username: str, password: str) -> dict | None:
    """Authenticate against the DB user store; returns the user row or None."""
    if store is None:
        return None
    user = store.get_user_by_username(username)
    if not user:
        return None
    if verify_password(password, user.get("password_hash", "")):
        return user
    return None


def bootstrap_admin(store: Any) -> bool:
    """Ensure a default tenant exists, then create an initial admin.

    Uses the SMART_CAM_ADMIN_PASSWORD env var (no default password is created).
    Returns True if a user was created.
    """
    import os
    if store is None:
        return False
    tid = store.ensure_default_tenant()
    if store.count_users() > 0:
        return False
    pw = os.environ.get("SMART_CAM_ADMIN_PASSWORD", "")
    if not pw:
        return False
    store.create_user("admin", hash_password(pw), role="admin", tenant_id=tid)
    return True
