"""Shared helpers."""
from __future__ import annotations

import hashlib
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np


def now_ts() -> float:
    return time.time()


def ts_to_iso(ts: float | None) -> str:
    if ts is None:
        return ""
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def format_duration(sec: float | None) -> str:
    if sec is None:
        return ""
    sec = int(sec)
    m, s = divmod(sec, 60)
    if m == 0:
        return f"{s}s"
    return f"{m}m {s:02d}s"


def resize_frame(frame: np.ndarray, max_width: int) -> np.ndarray:
    h, w = frame.shape[:2]
    if w <= max_width:
        return frame
    scale = max_width / w
    new_w = int(w * scale)
    new_h = int(h * scale)
    return np.ascontiguousarray(_resize(frame, new_w, new_h))


def _resize(frame: np.ndarray, w: int, h: int) -> np.ndarray:
    import cv2

    return cv2.resize(frame, (w, h), interpolation=cv2.INTER_AREA)


def save_thumbnail(frame: np.ndarray, path: str | Path, max_width: int = 640) -> Path:
    import cv2

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    img = resize_frame(frame, max_width)
    ok = cv2.imwrite(str(p), img, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
    if not ok:
        # fallback: PNG
        p = p.with_suffix(".png")
        cv2.imwrite(str(p), img)
    return p


def class_color(label: str) -> tuple[int, int, int]:
    """Deterministic BGR color for a class label."""
    h = int(hashlib.md5(label.encode()).hexdigest(), 16)
    return (h % 256, (h >> 8) % 256, (h >> 16) % 256)


def draw_detections(frame: np.ndarray, detections, names: dict[int, str] | None = None) -> np.ndarray:
    """Draw boxes/labels for a list of Detection objects (BGR frame)."""
    import cv2

    img = frame.copy()
    for d in detections:
        x1, y1, x2, y2 = [int(v) for v in d.xyxy]
        color = class_color(d.label)
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        tid = f"#{d.track_id}" if d.track_id is not None else ""
        text = f"{d.label}{tid} {d.conf:.2f}"
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(img, (x1, y1 - th - 6), (x1 + tw + 4, y1), color, -1)
        cv2.putText(img, text, (x1 + 2, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    return img


def draw_timestamp(frame: np.ndarray, text: str = "") -> np.ndarray:
    import cv2

    img = frame.copy()
    label = text or ts_to_iso(now_ts())
    h, w = img.shape[:2]
    cv2.rectangle(img, (0, h - 28), (min(280, w), h), (0, 0, 0), -1)
    cv2.putText(img, label, (8, h - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    return img


def extract_keyframes(clip_path: str | Path, out_prefix: str | Path, n: int = 3, max_side: int = 768) -> list[str]:
    """Extract n evenly spaced keyframes from a clip; return saved JPEG paths."""
    import cv2

    cap = cv2.VideoCapture(str(clip_path))
    if not cap.isOpened():
        return []
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    paths: list[str] = []
    for i in range(n):
        pos = int(total * (i + 1) / (n + 1))
        cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
        ok, frame = cap.read()
        if ok:
            frame = resize_frame(frame, max_side)
            p = Path(f"{out_prefix}_kf{i}.jpg")
            p.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(p), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
            paths.append(str(p))
    cap.release()
    return paths


def extract_frame(clip_path: str | Path, seconds: float) -> np.ndarray | None:
    """Return the frame at *seconds* into a video, or None."""
    import cv2

    cap = cv2.VideoCapture(str(clip_path))
    if not cap.isOpened():
        return None
    fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(seconds * fps))
    ok, frame = cap.read()
    cap.release()
    return frame if ok else None


def frame_to_jpeg_bytes(frame: np.ndarray, quality: int = 80) -> bytes:
    import cv2

    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        return b""
    return buf.tobytes()


def setup_logging(log_dir: str | Path, level: int = 20) -> None:
    """Configure file + console logging exactly once per process."""
    import logging
    from logging.handlers import RotatingFileHandler

    if getattr(setup_logging, "_configured", False):
        return
    setup_logging._configured = True  # type: ignore[attr-defined]

    root = logging.getLogger()
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
    fh = RotatingFileHandler(log_dir / "smartcam.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    fh.setFormatter(fmt)
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    root.setLevel(level)
    root.addHandler(fh)
    root.addHandler(ch)
