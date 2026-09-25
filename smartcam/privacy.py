"""Privacy blurring of faces/bodies (GDPR-friendly)."""
from __future__ import annotations

import numpy as np

from .config import PrivacyConfig
from .detector import Detection


class PrivacyBlur:
    def __init__(self, cfg: PrivacyConfig):
        self.cfg = cfg
        self._cascade = None
        if cfg.blur_enabled and cfg.blur_mode == "face":
            import cv2

            try:
                # OpenCV >= 5.0 removed the legacy Haar cascade API; if absent we
                # fall back to blurring the head region of each person box.
                path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                self._cascade = cv2.CascadeClassifier(path)
            except Exception:
                self._cascade = None

    def apply(self, frame: np.ndarray, detections: list[Detection]) -> np.ndarray:
        if not self.cfg.blur_enabled:
            return frame
        import cv2

        img = frame
        for d in detections:
            if d.label != "person":
                continue
            x1, y1, x2, y2 = [int(v) for v in d.xyxy]
            if self.cfg.blur_mode == "body":
                img = self._blur_region(img, x1, y1, x2, y2)
            else:
                img = self._blur_faces(img, x1, y1, x2, y2)
        return img

    def _blur_faces(self, img: np.ndarray, x1: int, y1: int, x2: int, y2: int):
        import cv2

        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(img.shape[1], x2), min(img.shape[0], y2)
        if x2 <= x1 or y2 <= y1:
            return img
        crop = img[y1:y2, x1:x2]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        faces = self._cascade.detectMultiScale(gray, 1.1, 4, minSize=(16, 16)) if self._cascade is not None else []
        if len(faces):
            for (fx, fy, fw, fh) in faces:
                img = self._blur_region(img, x1 + fx, y1 + fy, x1 + fx + fw, y1 + fy + fh)
        else:
            # fallback: blur the head region (top 20% of the person box)
            head_h = max(1, int((y2 - y1) * 0.22))
            img = self._blur_region(img, x1, y1, x2, y1 + head_h)
        return img

    @staticmethod
    def _blur_region(img: np.ndarray, x1: int, y1: int, x2: int, y2: int):
        import cv2

        x1, y1 = max(0, int(x1)), max(0, int(y1))
        x2, y2 = min(img.shape[1], int(x2)), min(img.shape[0], int(y2))
        if x2 - x1 < 2 or y2 - y1 < 2:
            return img
        roi = img[y1:y2, x1:x2]
        h, w = roi.shape[:2]
        small = cv2.resize(roi, (max(1, w // 12), max(1, h // 12)), interpolation=cv2.INTER_LINEAR)
        blocky = cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)
        img[y1:y2, x1:x2] = blocky
        return img
