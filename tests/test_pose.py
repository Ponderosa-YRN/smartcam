"""Smoke test: load the pose model and run torso-angle on a frame."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2

from smartcam.pose import PoseDetector

cap = cv2.VideoCapture("demo/demo.avi")
ok, frame = cap.read()
cap.release()
assert ok, "could not read demo frame"

pd = PoseDetector("yolov8n-pose.pt")
angle = pd.torso_angle(frame)
print("torso angle (full frame):", angle)
print("POSE TEST DONE")
