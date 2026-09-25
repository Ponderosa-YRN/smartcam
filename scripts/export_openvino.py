"""Export a YOLOv8 model to OpenVINO for Intel acceleration.

Requires the 'openvino' package (pip install openvino). Produces a
yolov8n_openvino_model/ directory; point detection.model at that directory to
run inference on Intel CPU/iGPU via the OpenVINO runtime.

Usage:
    .venv\\Scripts\\python scripts\\export_openvino.py [--model yolov8n.pt]
"""
from __future__ import annotations

import argparse


def main() -> None:
    ap = argparse.ArgumentParser(description="Export a YOLOv8 model to OpenVINO")
    ap.add_argument("--model", default="yolov8n.pt", help="Ultralytics model (e.g. yolov8n.pt, yolov8s.pt)")
    args = ap.parse_args()

    from ultralytics import YOLO

    model = YOLO(args.model)
    out = model.export(format="openvino", half=True)
    print("OpenVINO model exported to:", out)


if __name__ == "__main__":
    main()
