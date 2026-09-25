"""Security primitives: password hashing and signed bearer tokens.

Dependency-free by design so this works on the CPU-only dev box without any
network installs:

- Password hashing uses the stdlib scrypt KDF (N=2**14, r=8, p=1) with a random
  per-password salt. Swap to argon2id (argon2-cffi) later if you prefer Argon2;
  the stored-string format keeps the parameters self-describing.
- Tokens are HMAC-signed, expiring tokens via itsdangerous (already a
  dependency of the stack). They are opaque bearer tokens carrying a small
  claims dict; a real JWT (PyJWT) can replace them without changing callers.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from pathlib import Path
from typing import Any

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

_SCRYPT_N = 1 << 14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32

_TOKEN_SALT = "smartcam-token-v1"


def hash_password(password: str) -> str:
    """Hash a password to a self-describing string: scrypt$N$r$p$salt$digest."""
    salt = os.urandom(16)
    dk = hashlib.scrypt(
        password.encode("utf-8"), salt=salt,
        n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_SCRYPT_DKLEN,
    )
    return "scrypt$%d$%d$%d$%s$%s" % (
        _SCRYPT_N, _SCRYPT_R, _SCRYPT_P,
        base64.urlsafe_b64encode(salt).decode(),
        base64.urlsafe_b64encode(dk).decode(),
    )


def verify_password(password: str, stored: str) -> bool:
    """Constant-time check of *password* against a hash produced by hash_password."""
    try:
        scheme, n_s, r_s, p_s, salt_b64, digest_b64 = stored.split("$")
    except (ValueError, AttributeError):
        return False
    if scheme != "scrypt":
        return False
    try:
        salt = base64.urlsafe_b64decode(salt_b64.encode())
        expected = base64.urlsafe_b64decode(digest_b64.encode())
        dk = hashlib.scrypt(
            password.encode("utf-8"), salt=salt,
            n=int(n_s), r=int(r_s), p=int(p_s), dklen=len(expected),
        )
    except Exception:
        return False
    return hmac.compare_digest(dk, expected)


def new_secret() -> str:
    """Return a fresh random signing secret (for JWT-equivalent token signing)."""
    return secrets.token_urlsafe(48)


def _serializer(secret: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        secret,
        salt=_TOKEN_SALT,
        signer_kwargs={"key_derivation": "hmac", "digest_method": hashlib.sha256},
    )


def create_token(payload: dict[str, Any], secret: str) -> str:
    """Sign *payload* into an opaque, URL-safe bearer token string."""
    return _serializer(secret).dumps(payload)


def load_or_create_secret(path: str | Path, env_var: str = "SMART_CAM_TOKEN_SECRET") -> str:
    """Return the signing secret from *env_var*, else load/create it at *path*."""
    env = os.environ.get(env_var)
    if env:
        return env
    p = Path(path)
    if p.exists():
        val = p.read_text(encoding="utf-8").strip()
        if val:
            return val
    secret = new_secret()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(secret, encoding="utf-8")
    return secret


def read_token(token: str, secret: str, max_age: int) -> dict[str, Any] | None:
    """Validate *token* and return its payload, or None if invalid/expired."""
    if max_age is not None and max_age <= 0:
        return None
    try:
        data = _serializer(secret).loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(data, dict):
        return None
    return data
