"""Export the YOLO model to ONNX for faster CPU/GPU inference.

Usage:
    .venv\\Scripts\\python scripts\\export_onnx.py --model yolov8n.pt

Then set detection.model to the .onnx path (e.g. "yolov8n.onnx") and install
onnxruntime. Ultralytics runs .onnx models automatically when onnxruntime is
available.
"""
from __future__ import annotations

import argparse

from ultralytics import YOLO


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="yolov8n.pt")
    ap.add_argument("--imgsz", type=int, default=640)
    args = ap.parse_args()

    model = YOLO(args.model)
    path = model.export(format="onnx", imgsz=args.imgsz)
    print("Exported:", path)
    print('Set config: "detection": { "model": "' + str(path) + '" }')
    print("Install onnxruntime: pip install onnxruntime")


if __name__ == "__main__":
    main()
