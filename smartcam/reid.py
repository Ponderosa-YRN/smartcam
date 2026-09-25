"""Person appearance embedding via torchreid OSNet (BoxMOT's ReID engine)."""
from __future__ import annotations

import logging

import numpy as np

from .config import ReidConfig

log = logging.getLogger("smartcam.reid")


class ReidEngine:
    """Lazy OSNet FeatureExtractor. Weights (~2MB) download on first use."""

    def __init__(self, cfg: ReidConfig):
        self.cfg = cfg
        self._extractor = None

    def _ensure(self) -> None:
        if self._extractor is None:
            from torchreid.utils import FeatureExtractor

            self._extractor = FeatureExtractor(model_name=self.cfg.model_name, device="cpu")

    def embed(self, crop: np.ndarray) -> np.ndarray | None:
        self._ensure()
        if crop is None or crop.size == 0:
            return None
        rgb = crop[:, :, ::-1] if crop.ndim == 3 and crop.shape[-1] == 3 else crop  # BGR -> RGB
        feats = self._extractor([rgb])
        if feats is None or len(feats) == 0:
            return None
        return np.asarray(feats[0], dtype=np.float32)

    @staticmethod
    def cosine(a, b) -> float:
        a = np.asarray(a, dtype=np.float32)
        b = np.asarray(b, dtype=np.float32)
        denom = float(np.linalg.norm(a) * np.linalg.norm(b))
        return float(np.dot(a, b)) / denom if denom > 1e-9 else 0.0
