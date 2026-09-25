"""Storage backends for clips and thumbnails.

Local disk is the default. An S3-compatible backend (AWS S3, MinIO, Cloudflare
R2, Backblaze B2) can be enabled via config; it imports boto3 lazily, so the
dependency is only required when S3 is actually used.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

log = logging.getLogger("smartcam.storage")


class StorageBackend:
    """Minimal object-storage interface."""

    provider = "local"

    def put(self, local_path: str | Path) -> str:
        """Store a local file and return a reference (a path or an object key)."""
        raise NotImplementedError

    def url(self, reference: str, expires: int = 3600) -> str:
        """Return a URL the API can serve/redirect to."""
        raise NotImplementedError

    def delete(self, reference: str) -> None:
        raise NotImplementedError


class LocalStorage(StorageBackend):
    """Files stay on local disk; the reference is just the path."""

    provider = "local"

    def put(self, local_path: str | Path) -> str:
        return str(local_path)

    def url(self, reference: str, expires: int = 3600) -> str:
        return reference

    def delete(self, reference: str) -> None:
        try:
            Path(reference).unlink(missing_ok=True)
        except OSError:
            pass


class S3Storage(StorageBackend):
    """S3-compatible object storage (lazy boto3 import)."""

    provider = "s3"

    def __init__(
        self,
        bucket: str,
        endpoint_url: str = "",
        region: str = "",
        access_key: str = "",
        secret_key: str = "",
        prefix: str = "",
    ):
        self.bucket = bucket
        self.endpoint_url = endpoint_url
        self.region = region
        self.access_key = access_key
        self.secret_key = secret_key
        self.prefix = prefix.rstrip("/")
        self._client = None

    def _s3(self):
        if self._client is None:
            import boto3  # lazy import

            kwargs: dict[str, Any] = {}
            if self.endpoint_url:
                kwargs["endpoint_url"] = self.endpoint_url
            if self.region:
                kwargs["region_name"] = self.region
            if self.access_key and self.secret_key:
                kwargs["aws_access_key_id"] = self.access_key
                kwargs["aws_secret_access_key"] = self.secret_key
            self._client = boto3.client("s3", **kwargs)
        return self._client

    def _key(self, local_path: str | Path) -> str:
        name = Path(local_path).name
        return (self.prefix + "/" + name) if self.prefix else name

    def put(self, local_path: str | Path) -> str:
        key = self._key(local_path)
        self._s3().upload_file(str(local_path), self.bucket, key)
        return key

    def url(self, reference: str, expires: int = 3600) -> str:
        return self._s3().generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": reference}, ExpiresIn=expires
        )

    def delete(self, reference: str) -> None:
        self._s3().delete_object(Bucket=self.bucket, Key=reference)


def get_storage(cfg) -> StorageBackend:
    """Return the configured storage backend (defaults to local)."""
    s = cfg.storage
    if s.provider == "s3":
        return S3Storage(
            bucket=s.bucket,
            endpoint_url=s.endpoint_url,
            region=s.region,
            access_key=s.access_key,
            secret_key=s.secret_key,
            prefix=s.prefix,
        )
    return LocalStorage()
