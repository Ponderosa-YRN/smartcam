"""Smart search: natural-language queries over recorded events.

Queries can mix object classes ("person", "car"), time-of-day words
("night", "morning"), and free text. No heavy embedding model is required:
we match object labels + summaries and rank by relevance and recency.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any

from .db import EventStore

# Fallback vocabulary when the detector's class names are not available.
FALLBACK_CLASSES = {
    "person": "person", "people": "person", "human": "person", "man": "person", "woman": "person",
    "car": "car", "cars": "car", "vehicle": "car", "truck": "truck", "bus": "bus",
    "motorcycle": "motorcycle", "motorbike": "motorcycle", "bike": "bicycle", "bicycle": "bicycle",
    "dog": "dog", "cat": "cat", "bird": "bird", "bag": "handbag", "backpack": "backpack",
    "suitcase": "suitcase", "umbrella": "umbrella",
}

TIME_OF_DAY = {
    "morning": (5, 11),
    "afternoon": (11, 16),
    "noon": (11, 16),
    "evening": (16, 20),
    "night": (20, 5),  # wraps midnight
    "day": (6, 18),
    "daytime": (6, 18),
}

DATE_TERMS = ("today", "yesterday", "week", "last-week", "this-week")


class SmartSearch:
    def __init__(self, store: EventStore, class_names: dict[int, str] | None = None):
        self.store = store
        self.lookup: dict[str, str] = dict(FALLBACK_CLASSES)
        for label in (class_names or {}).values():
            self.lookup.setdefault(str(label).lower(), str(label).lower())

    def parse(self, query: str) -> dict[str, Any]:
        q = (query or "").strip().lower()
        terms: list[str] = []
        classes: list[str] = []
        tod: tuple[int, int] | None = None
        date_range: tuple[float, float] | None = None

        for tok in q.split():
            tok = tok.strip(",.!?;:'\"()")
            if not tok:
                continue
            if tok in self.lookup:
                cls = self.lookup[tok]
                if cls not in classes:
                    classes.append(cls)
            elif tok in TIME_OF_DAY:
                tod = TIME_OF_DAY[tok]
            elif tok in DATE_TERMS:
                date_range = self._date_range(tok)
            else:
                terms.append(tok)
        return {"terms": terms, "classes": classes, "tod": tod, "date_range": date_range}

    def run(self, query: str, limit: int = 100, camera_id: str | None = None, tenant_id: int | None = None) -> list[dict[str, Any]]:
        parsed = self.parse(query)
        if parsed["terms"]:
            events = self.store.search(parsed["terms"], limit=1000, tenant_id=tenant_id)
        else:
            events = self.store.list_events(limit=1000, tenant_id=tenant_id)
        scored: list[tuple[float, dict[str, Any]]] = []
        for ev in events:
            if camera_id and ev.get("camera_id") != camera_id:
                continue
            if not self._matches_time(ev, parsed["tod"], parsed["date_range"]):
                continue
            if not self._matches_classes(ev, parsed["classes"]):
                continue
            scored.append((self._score(ev, parsed), ev))
        scored.sort(key=lambda pair: (-pair[0], -(pair[1].get("start_ts") or 0)))
        return [ev for _, ev in scored[:limit]]

    # -- helpers ----------------------------------------------------------
    @staticmethod
    def _matches_classes(event: dict[str, Any], classes: list[str]) -> bool:
        if not classes:
            return True
        objs = {str(o).lower() for o in (event.get("objects") or [])}
        top = str(event.get("top_object") or "").lower()
        return any(c in objs or c == top for c in classes)

    def _score(self, event: dict[str, Any], parsed: dict[str, Any]) -> float:
        score = 0.0
        objs = [str(o).lower() for o in (event.get("objects") or [])]
        top = str(event.get("top_object") or "").lower()
        summary = str(event.get("summary") or "").lower()
        for cls in parsed["classes"]:
            if cls in objs:
                score += 5
            elif cls == top:
                score += 3
        for term in parsed["terms"]:
            if any(term in o for o in objs) or term in top or term in summary:
                score += 2
        # recency bonus (small)
        start = event.get("start_ts") or 0
        score += max(0.0, 0.5 - (time.time() - start) / (7 * 86400))
        return score

    @staticmethod
    def _matches_time(event: dict[str, Any], tod: tuple[int, int] | None, date_range: tuple[float, float] | None) -> bool:
        start = event.get("start_ts")
        if start is None:
            return tod is None and date_range is None
        if date_range is not None:
            lo, hi = date_range
            if not (lo <= start < hi):
                return False
        if tod is not None:
            h = datetime.fromtimestamp(start).hour
            lo, hi = tod
            if lo < hi:
                if not (lo <= h < hi):
                    return False
            else:  # wraps midnight, e.g. night 20:00-05:00
                if not (h >= lo or h < hi):
                    return False
        return True

    @staticmethod
    def _date_range(term: str) -> tuple[float, float]:
        now = datetime.now()
        if term == "today":
            lo = datetime(now.year, now.month, now.day)
            return lo.timestamp(), (lo + timedelta(days=1)).timestamp()
        if term == "yesterday":
            lo = datetime(now.year, now.month, now.day) - timedelta(days=1)
            return lo.timestamp(), (lo + timedelta(days=1)).timestamp()
        # "week" / "this-week" / "last-week"
        lo = datetime(now.year, now.month, now.day) - timedelta(days=7)
        return lo.timestamp(), (lo + timedelta(days=1)).timestamp()
