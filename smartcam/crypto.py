"""Encryption-at-rest helpers (Fernet). Requires the cryptography package."""
from __future__ import annotations

from pathlib import Path


def generate_key() -> str:
    from cryptography.fernet import Fernet

    return Fernet.generate_key().decode()


def encrypt_file(path: str | Path, key: str) -> Path:
    from cryptography.fernet import Fernet

    p = Path(path)
    f = Fernet(key.encode() if isinstance(key, str) else key)
    p.write_bytes(f.encrypt(p.read_bytes()))
    return p


def decrypt_file(path: str | Path, key: str) -> bytes:
    from cryptography.fernet import Fernet

    f = Fernet(key.encode() if isinstance(key, str) else key)
    return f.decrypt(Path(path).read_bytes())
