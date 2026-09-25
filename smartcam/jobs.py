"""Bounded background job queue with backpressure (drop-oldest when full)."""
from __future__ import annotations

import logging
import queue
import threading
from typing import Any

log = logging.getLogger("smartcam.jobs")


class BoundedQueue:
    """A bounded queue that drops the OLDEST job when full, so heavy workers
    (OCR, embedding) can never grow memory unboundedly."""

    def __init__(self, maxsize: int = 64):
        self.maxsize = maxsize
        self._q = queue.Queue(maxsize=maxsize)

    def put(self, item: Any) -> bool:
        try:
            self._q.put_nowait(item)
            return True
        except queue.Full:
            try:
                self._q.get_nowait()  # drop the oldest
            except queue.Empty:
                pass
            try:
                self._q.put_nowait(item)
            except queue.Full:
                return False
            return True

    def get(self, timeout: float = 1.0):
        return self._q.get(timeout=timeout)

    def qsize(self) -> int:
        return self._q.qsize()


class JobPool:
    """A bounded worker pool for background jobs (summaries, notifications, webhooks).

    Workers pull (fn, args) tuples off a BoundedQueue so a slow job (e.g. a VLM
    HTTP call) never blocks the detection hot path, and the queue drops its
    oldest job instead of growing unboundedly under load.
    """

    def __init__(self, workers: int = 2, maxsize: int = 256):
        self.workers = max(1, workers)
        self._q = BoundedQueue(maxsize=maxsize)
        self._threads = [
            threading.Thread(target=self._run, name=f"jobpool-{i}", daemon=True)
            for i in range(self.workers)
        ]
        for t in self._threads:
            t.start()

    def _run(self) -> None:
        while True:
            try:
                fn, args = self._q.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                fn(*args)
            except Exception as exc:
                log.warning("job failed: %s", exc)

    def submit(self, fn, *args) -> bool:
        return self._q.put((fn, args))

    def pending(self) -> int:
        return self._q.qsize()
