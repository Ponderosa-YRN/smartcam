"""Test the ApiClient against a running SmartCam API."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from smartcam.client import ApiClient

c = ApiClient("http://localhost:8000")

sources = [(s.id, s.name) for s in c.cfg.sources]
print("sources:", sources)
assert len(sources) >= 1, "no sources from API"

print("class names count:", len(c.detector.names))
assert len(c.detector.names) > 0

print("events (limit 5):", len(c.store.list_events(limit=5)))
print("event count:", c.store.count_events())
print("search 'person':", len(c.search("person", limit=5)))
print("plates:", len(c.store.list_plates(limit=5)))
print("identities:", len(c.store.list_identities()))
print("status:", c.pipelines[sources[0][0]].stats["status"])

print("CLIENT TEST PASSED")
