"""WebRTC helpers (dependency-free parts)."""

import numpy as np

from smartcam.config import WebRTCConfig
from smartcam.webrtc import available, grab_rgb, ice_server_dicts, make_track


class _FakePipeline:
    def __init__(self, frame):
        self.latest_frame = frame


def test_grab_rgb_converts_bgr_to_rgb():
    bgr = np.zeros((4, 6, 3), dtype=np.uint8)
    bgr[..., 0] = 255  # blue
    bgr[..., 1] = 128  # green
    rgb = grab_rgb(_FakePipeline(bgr))
    assert rgb.shape == (4, 6, 3)
    assert int(rgb[0, 0, 0]) == 0    # red
    assert int(rgb[0, 0, 1]) == 128  # green (unchanged)
    assert int(rgb[0, 0, 2]) == 255  # blue moved to red


def test_grab_rgb_falls_back_to_black_frame():
    rgb = grab_rgb(_FakePipeline(None))
    assert rgb.shape == (480, 640, 3)
    assert (rgb == 0).all()


def test_available_returns_bool():
    assert isinstance(available(), bool)


def test_make_track_when_available():
    if not available():
        return  # aiortc not installed; the endpoint degrades gracefully
    track = make_track(_FakePipeline(None))
    assert track.kind == "video"


def test_ice_server_dicts_default_stun():
    servers = ice_server_dicts(WebRTCConfig())
    assert servers == [{"urls": "stun:stun.l.google.com:19302"}]


def test_ice_server_dicts_with_turn():
    cfg = WebRTCConfig(turn_url="turn:turn.example.com:3478", turn_username="u", turn_credential="p")
    servers = ice_server_dicts(cfg)
    assert len(servers) == 2
    assert servers[0] == {"urls": "stun:stun.l.google.com:19302"}
    assert servers[1] == {"urls": "turn:turn.example.com:3478", "username": "u", "credential": "p"}
