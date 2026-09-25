"""Minimal diagnostic: read one frame, run predict() and track()."""
import sys, traceback
import cv2
print("cv2", cv2.__version__)

cap = cv2.VideoCapture("demo/demo.avi")
ok, frame = cap.read()
print("read frame:", ok, "shape:", None if frame is None else frame.shape)
cap.release()

if not ok:
    sys.exit("could not read frame")

from ultralytics import YOLO
model = YOLO("yolov8n.pt")
print("model names count:", len(model.names))

# 1) predict only
try:
    res = model.predict(frame, imgsz=640, conf=0.25, verbose=False)
    r = res[0]
    print("predict detections:", 0 if r.boxes is None else len(r.boxes))
except Exception:
    print("PREDICT FAILED:")
    traceback.print_exc()

# 2) track
try:
    res = model.track(frame, persist=True, tracker="bytetrack.yaml", imgsz=640, conf=0.25, verbose=False)
    r = res[0]
    n = 0 if r.boxes is None else len(r.boxes)
    ids = None if (r.boxes is None or r.boxes.id is None) else r.boxes.id.tolist()
    print("track detections:", n, "track_ids:", ids)
except Exception:
    print("TRACK FAILED:")
    traceback.print_exc()
