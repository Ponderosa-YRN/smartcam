"""Storage backend tests (local + config round-trip + S3 key logic)."""
import os
import tempfile

from smartcam.config import config_from_dict, load_config
from smartcam.storage import LocalStorage, S3Storage, get_storage


def test_local_storage():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "clip.mp4")
    with open(p, "w") as f:
        f.write("x")
    s = LocalStorage()
    ref = s.put(p)
    assert ref == p
    assert s.url(ref) == ref
    s.delete(ref)
    assert not os.path.exists(p)


def test_s3_key_logic():
    s = S3Storage(bucket="b", prefix="clips")
    assert s._key("/tmp/foo/bar.mp4") == "clips/bar.mp4"
    s2 = S3Storage(bucket="b", prefix="")
    assert s2._key("/tmp/bar.mp4") == "bar.mp4"
    assert s2.provider == "s3"


def test_get_storage():
    cfg = config_from_dict({"storage": {"provider": "s3", "bucket": "b", "prefix": "clips"}})
    s = get_storage(cfg)
    assert s.provider == "s3" and s.bucket == "b"
    cfg2 = load_config(os.path.join(tempfile.gettempdir(), "nope.json"))
    assert get_storage(cfg2).provider == "local"
