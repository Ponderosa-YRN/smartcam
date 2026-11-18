"""The frame overlay runs on every frame of every camera, so it must never raise.

A crash here does not lose a detection - it stops the annotation, which is what the live
view and the saved clips show.
"""
from types import SimpleNamespace

import numpy as np

from smartcam.utils import draw_detections, draw_timestamp

FRAME = np.full((360, 640, 3), 90, dtype=np.uint8)


def det(x1=100, y1=80, x2=220, y2=300, label="person", conf=0.87, track_id=4):
    return SimpleNamespace(xyxy=[x1, y1, x2, y2], label=label, conf=conf, track_id=track_id)


def test_draws_without_changing_size_or_the_input_frame():
    before = FRAME.copy()
    out = draw_detections(FRAME, [det()])
    assert out.shape == FRAME.shape
    assert (FRAME == before).all(), "the source frame must not be modified"
    assert (out != FRAME).any()


def test_label_at_the_top_edge_does_not_go_off_frame():
    """y1=0 puts the label above the image; the drawing must flip it inside instead."""
    out = draw_detections(FRAME, [det(y1=0)])
    assert out.shape == FRAME.shape
    assert (out != FRAME).any()


def test_a_box_at_the_bottom_edge_does_not_raise():
    out = draw_detections(FRAME, [det(y1=200, y2=360)])
    assert out.shape == FRAME.shape


def test_empty_detections_is_a_plain_copy():
    out = draw_detections(FRAME, [])
    assert out.shape == FRAME.shape
    assert (out == FRAME).all()


def test_a_tiny_box_does_not_produce_negative_corner_lengths():
    out = draw_detections(FRAME, [det(x1=10, y1=10, x2=12, y2=12)])
    assert out.shape == FRAME.shape


def test_timestamp_keeps_the_frame_size():
    out = draw_timestamp(FRAME, "2026-11-18 22:40:00")
    assert out.shape == FRAME.shape
    assert (out != FRAME).any()
