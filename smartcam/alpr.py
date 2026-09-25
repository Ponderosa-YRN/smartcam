"""License-plate (ANPR) reading via EasyOCR, with an optional plate detector."""
from __future__ import annotations

import logging
import re

import numpy as np

from .config import AlprConfig

log = logging.getLogger("smartcam.alpr")

_PLATE_RE = re.compile(r"^[A-Z0-9]{4,10}$")


def _is_plate(text: str) -> bool:
    return (
        _PLATE_RE.match(text) is not None
        and any(c.isdigit() for c in text)
        and any(c.isalpha() for c in text)
    )


class AlprReader:
    """Lazy EasyOCR wrapper. The ~50MB OCR model downloads on first use."""

    def __init__(self, cfg: AlprConfig):
        self.cfg = cfg
        self._reader = None
        self._plate_model = None

    def _ensure(self) -> None:
        if self._reader is None:
            import easyocr

            langs = [l.strip() for l in self.cfg.languages.split(",") if l.strip()] or ["en"]
            self._reader = easyocr.Reader(langs, gpu=False, verbose=False)
        if self.cfg.plate_model and self._plate_model is None:
            from ultralytics import YOLO

            self._plate_model = YOLO(self.cfg.plate_model)

    def read_plate(self, vehicle_crop: np.ndarray) -> tuple[str | None, float, np.ndarray | None]:
        """Return (plate_text, confidence, plate_crop). Text is None if unreadable."""
        self._ensure()
        img = vehicle_crop
        crop = img
        if self._plate_model is not None:
            res = self._plate_model.predict(img, conf=0.25, verbose=False)
            if res and res[0].boxes is not None and len(res[0].boxes):
                box = res[0].boxes.xyxy[0].cpu().numpy()
                x1, y1, x2, y2 = [int(v) for v in box]
                if x2 > x1 and y2 > y1:
                    crop = img[y1:y2, x1:x2]
        if crop is None or crop.size == 0:
            return None, 0.0, None
        results = self._reader.readtext(crop, detail=1, paragraph=False)
        best: tuple[str, float] | None = None
        for (_bbox, text, conf) in results:
            t = re.sub(r"[^A-Z0-9]", "", str(text).upper())
            if _is_plate(t):
                if best is None or conf > best[1]:
                    best = (t, float(conf))
        if best is not None and best[1] >= self.cfg.min_conf:
            return best[0], best[1], crop
        return None, 0.0, crop
