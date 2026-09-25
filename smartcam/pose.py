"""Pose estimation for fall detection (YOLOv8-pose)."""
from __future__ import annotations

import logging
import math

import numpy as np

log = logging.getLogger("smartcam.pose")

L_SHOULDER, R_SHOULDER = 5, 6
L_HIP, R_HIP = 11, 12
_KEY_IDX = [L_SHOULDER, R_SHOULDER, L_HIP, R_HIP]


class PoseDetector:
    """Wraps YOLOv8-pose and reports the torso angle (from vertical) in degrees."""

    def __init__(self, model: str = "yolov8n-pose.pt"):
        from ultralytics import YOLO

        self.model = YOLO(model)

    def torso_angle(self, crop: np.ndarray) -> float | None:
        """Return torso angle from vertical (degrees), or None if unclear."""
        res = self.model.predict(crop, conf=0.3, verbose=False)
        if not res:
            return None
        r = res[0]
        if r.keypoints is None or getattr(r.keypoints, "xy", None) is None or len(r.keypoints.xy) == 0:
            return None
        k = r.keypoints.xy[0].cpu().numpy()
        conf = r.keypoints.conf
        if conf is not None and len(conf) and any(float(conf[0][i]) < 0.3 for i in _KEY_IDX):
            return None
        sh_x = (k[L_SHOULDER][0] + k[R_SHOULDER][0]) / 2.0
        sh_y = (k[L_SHOULDER][1] + k[R_SHOULDER][1]) / 2.0
        hp_x = (k[L_HIP][0] + k[R_HIP][0]) / 2.0
        hp_y = (k[L_HIP][1] + k[R_HIP][1]) / 2.0
        dx = hp_x - sh_x
        dy = hp_y - sh_y
        if abs(dy) < 1e-6:
            return 90.0
        return math.degrees(math.atan2(abs(dx), abs(dy)))
