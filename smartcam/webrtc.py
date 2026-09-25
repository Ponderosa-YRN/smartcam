"""WebRTC low-latency live streaming for SmartCam.

Lazy-loads aiortc so the rest of the app runs fine without it. The signaling
flow lives in api.py (ws /ws/webrtc/{source_id}); this module provides the
dependency probe and the video track that sources frames from a camera pipeline.
"""
from __future__ import annotations

import logging

log = logging.getLogger("smartcam.webrtc")


def available() -> bool:
    """True if the aiortc + av stack is importable."""
    try:
        import aiortc  # noqa: F401
        import av  # noqa: F401

        return True
    except Exception:
        return False


def grab_rgb(pipeline):
    """Return the pipeline's latest frame as an RGB ndarray (or a black placeholder)."""
    import numpy as np

    frame = getattr(pipeline, "latest_frame", None)
    if frame is None:
        return np.zeros((480, 640, 3), dtype=np.uint8)
    return np.ascontiguousarray(frame[:, :, ::-1])  # BGR -> RGB


def make_track(pipeline, fps: float = 10.0):
    """Build an aiortc VideoStreamTrack that streams the pipeline's latest frame."""
    import asyncio

    from aiortc.mediastreams import VideoStreamTrack
    from av import VideoFrame

    class _Track(VideoStreamTrack):
        kind = "video"

        async def recv(self):
            pts, time_base = await self.next_timestamp()
            vf = VideoFrame.from_ndarray(grab_rgb(pipeline), format="rgb24")
            vf.pts = pts
            vf.time_base = time_base
            await asyncio.sleep(1.0 / max(1.0, fps))
            return vf

    return _Track()


def ice_server_dicts(cfg) -> list[dict]:
    """Return ICE server dicts (STUN + optional TURN) for a WebRTCConfig."""
    stun = getattr(cfg, "stun_urls", None)
    if isinstance(stun, str):
        stun = [stun]
    servers = [{"urls": u} for u in (stun or [])]
    turn = getattr(cfg, "turn_url", "")
    if turn:
        servers.append({
            "urls": turn,
            "username": getattr(cfg, "turn_username", "") or "",
            "credential": getattr(cfg, "turn_credential", "") or "",
        })
    return servers


def make_configuration(cfg):
    """Build an aiortc RTCConfiguration from a WebRTCConfig."""
    from aiortc import RTCConfiguration, RTCIceServer

    servers = []
    for d in ice_server_dicts(cfg):
        kw = {"urls": d["urls"]}
        if d.get("username"):
            kw["username"] = d["username"]
        if d.get("credential"):
            kw["credential"] = d["credential"]
        servers.append(RTCIceServer(**kw))
    return RTCConfiguration(iceServers=servers)
