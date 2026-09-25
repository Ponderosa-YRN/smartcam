"""Job pool + detector device resolution tests."""

import time

from smartcam.detector import resolve_device
from smartcam.jobs import BoundedQueue, JobPool


def test_resolve_device():
    assert resolve_device("cpu") == "cpu"
    assert resolve_device("cuda", cuda_available=True) == "cuda"
    assert resolve_device("cuda", cuda_available=False) == "cpu"
    assert resolve_device("mps", mps_available=True) == "mps"
    assert resolve_device("mps", mps_available=False) == "cpu"
    assert resolve_device("auto", cuda_available=True) == "cuda"
    assert resolve_device("auto", mps_available=True) == "mps"
    assert resolve_device("auto") == "cpu"
    assert resolve_device("bogus") == "cpu"
    assert resolve_device("") == "cpu"


def test_bounded_queue_drops_oldest():
    q = BoundedQueue(maxsize=2)
    assert q.put("a") is True
    assert q.put("b") is True
    assert q.put("c") is True  # drops "a"
    assert q.get(timeout=0.1) == "b"
    assert q.get(timeout=0.1) == "c"


def test_job_pool_executes():
    results = []
    pool = JobPool(workers=2, maxsize=16)
    pool.submit(lambda x: results.append(x), 1)
    pool.submit(lambda x: results.append(x), 2)
    for _ in range(100):
        if len(results) >= 2:
            break
        time.sleep(0.02)
    assert sorted(results) == [1, 2]
