"""Generate a small synthetic clip (moving shapes) for offline pipeline tests.

This exercises frame reading, clip writing, and event recording mechanics
without needing a real camera. For actual object detection demos, use
scripts/download_demo.py to fetch a clip that contains people/vehicles.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np


def main(out: str = "demo/synthetic.mp4", seconds: int = 20, fps: int = 30) -> None:
    import cv2

    w, h = 960, 540
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(out, fourcc, fps, (w, h))
    if not writer.isOpened():
        print("mp4v writer failed, trying avi/XVID")
        writer = cv2.VideoWriter(out.replace(".mp4", ".avi"), cv2.VideoWriter_fourcc(*"XVID"), fps, (w, h))

    n_frames = seconds * fps
    for i in range(n_frames):
        t = i / fps
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        # static "scene"
        cv2.rectangle(frame, (0, int(h * 0.6)), (w, h), (90, 90, 90), -1)
        cv2.rectangle(frame, (50, 120), (230, 320), (60, 60, 80), -1)
        cv2.rectangle(frame, (650, 80), (900, 320), (50, 70, 60), -1)

        # moving object 1 (horizontal sweep)
        x1 = int((t * 45) % (w + 200)) - 100
        cv2.circle(frame, (x1, int(h * 0.55)), 26, (0, 0, 255), -1)
        # moving object 2 (vertical bounce)
        y2 = int(h * 0.4 + 60 * math.sin(t * 1.5))
        cv2.rectangle(frame, (600, y2 - 20), (650, y2 + 20), (0, 255, 0), -1)
        # moving object 3 (diagonal)
        x3 = int((t * 30) % (w + 200)) - 100
        y3 = int(h * 0.45 + 80 * math.sin(t * 0.8 + 1))
        cv2.circle(frame, (x3, y3), 16, (255, 0, 0), -1)

        cv2.putText(frame, f"t={t:.1f}s", (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
        writer.write(frame)

    writer.release()
    print(f"wrote {out} ({n_frames} frames)")


if __name__ == "__main__":
    main(*sys.argv[1:])
