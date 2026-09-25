"""YOLOv8 detection + multi-object tracking."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

from .config import DetectionConfig

log = logging.getLogger("smartcam.detector")


def resolve_device(requested: str, cuda_available: bool = False, mps_available: bool = False) -> str:
    """Return the effective torch device for a model, falling back to cpu.

    'openvino' is handled via an exported OpenVINO model directory (see
    scripts/export_openvino.py), not a torch device, so it maps to cpu here.
    """
    req = (requested or "auto").strip().lower()
    if req == "cuda":
        return "cuda" if cuda_available else "cpu"
    if req == "mps":
        return "mps" if mps_available else "cpu"
    if req == "cpu":
        return "cpu"
    if req == "auto":
        if cuda_available:
            return "cuda"
        if mps_available:
            return "mps"
        return "cpu"
    return "cpu"


def _torch_capabilities() -> tuple[bool, bool]:
    try:
        import torch

        cuda = bool(torch.cuda.is_available())
        mps = bool(getattr(torch.backends, "mps", None) and torch.backends.mps.is_available())
        return cuda, mps
    except Exception:
        return False, False


@dataclass
class Detection:
    xyxy: list[float]  # x1, y1, x2, y2 (pixels)
    cls: int
    label: str
    conf: float
    track_id: int | None = None


class Detector:
    """Thin wrapper around ultralytics YOLO with ByteTrack persistence."""

    def __init__(self, cfg: DetectionConfig):
        from ultralytics import YOLO  # imported lazily so UI can load fast

        self.cfg = cfg
        cuda, mps = _torch_capabilities()
        self.device = resolve_device(cfg.device, cuda, mps)
        log.info("detector device: %s (requested %s)", self.device, cfg.device)
        self.model = YOLO(cfg.model)
        self.names: dict[int, str] = self.model.names  # {idx: label}
        self._warmed_up = False

    def warmup(self, imgsz: int = 640) -> None:
        if self._warmed_up:
            return
        dummy = np.zeros((imgsz, imgsz, 3), dtype=np.uint8)
        self.model.predict(dummy, imgsz=imgsz, verbose=False, device=self.device)
        self._warmed_up = True

    def track(self, frame: np.ndarray, imgsz: int | None = None) -> list[Detection]:
        """Run tracking on a BGR frame and return a list of Detection."""
        results = self.model.track(
            frame,
            persist=True,
            tracker=self.cfg.tracker,
            conf=self.cfg.conf,
            iou=self.cfg.iou,
            imgsz=imgsz or self.cfg.imgsz,
            classes=self.cfg.classes or None,
            device=self.device,
            verbose=False,
        )
        detections: list[Detection] = []
        if not results:
            return detections
        result = results[0]
        if result.boxes is None or len(result.boxes) == 0:
            return detections

        boxes = result.boxes.xyxy.cpu().numpy() if hasattr(result.boxes.xyxy, "cpu") else result.boxes.xyxy.numpy()
        classes = result.boxes.cls.cpu().numpy() if hasattr(result.boxes.cls, "cpu") else result.boxes.cls.numpy()
        confs = result.boxes.conf.cpu().numpy() if hasattr(result.boxes.conf, "cpu") else result.boxes.conf.numpy()
        ids = None
        if result.boxes.id is not None:
            ids = result.boxes.id.cpu().numpy() if hasattr(result.boxes.id, "cpu") else result.boxes.id.numpy()

        for i in range(len(boxes)):
            cls_id = int(classes[i])
            detections.append(
                Detection(
                    xyxy=[float(v) for v in boxes[i]],
                    cls=cls_id,
                    label=self.names.get(cls_id, str(cls_id)),
                    conf=float(confs[i]),
                    track_id=int(ids[i]) if ids is not None else None,
                )
            )
        return detections

    def annotate(self, frame: np.ndarray) -> np.ndarray:
        """Return an annotated BGR frame (convenience for the live view)."""
        results = self.model.track(
            frame,
            persist=True,
            tracker=self.cfg.tracker,
            conf=self.cfg.conf,
            iou=self.cfg.iou,
            imgsz=self.cfg.imgsz,
            classes=self.cfg.classes or None,
            device=self.device,
            verbose=False,
        )
        if not results:
            return frame
        plotted = results[0].plot()
        return plotted
