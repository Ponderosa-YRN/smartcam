"""Face recognition: detection + embedding via deepface, cosine matching."""
from __future__ import annotations

import logging

import numpy as np

from .config import FaceConfig

log = logging.getLogger("smartcam.face")


class FaceEngine:
    """Lazy deepface wrapper. Models download on first use."""

    def __init__(self, cfg: FaceConfig):
        self.cfg = cfg
        self._deepface = None

    def _ensure(self) -> None:
        if self._deepface is None:
            from deepface import DeepFace

            self._deepface = DeepFace

    def detect_and_embed(self, image: np.ndarray) -> list[dict]:
        """Return [{embedding, box}], one per detected face."""
        self._ensure()
        results = self._deepface.represent(
            image,
            model_name=self.cfg.model_name,
            detector_backend=self.cfg.detector_backend,
            enforce_detection=False,
            align=True,
        )
        out: list[dict] = []
        for r in results:
            emb = np.asarray(r["embedding"], dtype=np.float32)
            area = r.get("facial_area") or {}
            x = float(area.get("x", 0))
            y = float(area.get("y", 0))
            w = float(area.get("w", 0))
            h = float(area.get("h", 0))
            out.append({"embedding": emb, "box": [x, y, x + w, y + h]})
        return out

    @staticmethod
    def cosine(a, b) -> float:
        a = np.asarray(a, dtype=np.float32)
        b = np.asarray(b, dtype=np.float32)
        denom = float(np.linalg.norm(a) * np.linalg.norm(b))
        return float(np.dot(a, b)) / denom if denom > 1e-9 else 0.0
