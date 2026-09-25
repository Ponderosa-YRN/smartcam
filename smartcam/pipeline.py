"""Real-time processing pipeline: source -> detect/track -> events -> clips.

Runs in a background thread and exposes the latest annotated frame and stats
for the live dashboard. Writes events and clips to the EventStore. Also hosts
hotel features: zone rules (loitering/queue/intrusion/parking), fall detection,
abandoned-object detection, privacy blurring, heatmap accumulation, retention,
and webhook delivery.
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any

import numpy as np

from .alpr import AlprReader
from .analytics import Heatmap
from .config import AppConfig, SourceConfig
from .jobs import BoundedQueue, JobPool
from .db import EventStore
from .detector import Detector, Detection
from .face import FaceEngine
from .notify import Notifier
from .privacy import PrivacyBlur
from .reid import ReidEngine
from .retention import purge as retention_purge
from .search import SmartSearch
from .summarize import VLMSummarizer
from .utils import draw_detections, draw_timestamp, extract_keyframes, now_ts, resize_frame, save_thumbnail
from .webhook import Webhook
from .zones import ZoneTracker, point_in_polygon

log = logging.getLogger("smartcam.pipeline")

MAX_CLIP_SEC = 180.0
TRACK_TIMEOUT_SEC = 5.0
STATIC_MOVE_PX = 15.0


class _OpenEvent:
    def __init__(self, event_id, start_ts, writer, thumb_frame, fps, clip_path=""):
        self.event_id = event_id
        self.start_ts = start_ts
        self.writer = writer
        self.thumb_frame = thumb_frame
        self.fps = fps
        self.clip_path = clip_path
        self.track_ids = set()
        self.objects = set()
        self.max_conf = 0.0
        self.last_trigger_seen = start_ts
        self.frames = 0


class CameraPipeline:
    def __init__(self, source, cfg, store, detector, notifier, summarizer, webhook=None, face_engine=None, reid_engine=None, jobs=None):
        self.source = source
        self.cfg = cfg
        self.store = store
        self.detector = detector
        self.notifier = notifier
        self.summarizer = summarizer
        self.webhook = webhook
        self.face_engine = face_engine
        self.reid_engine = reid_engine

        self._running = False
        self._thread = None
        self._lock = threading.Lock()

        self.latest_frame = None
        self.stats = {
            "status": "stopped", "fps": 0.0, "frames": 0,
            "active_objects": [], "object_counts": {}, "zones": [], "last_event": None, "error": "", "last_frame_ts": None,
            "entered": 0, "left": 0,
        }

        self._last_dets = []
        self._track_meta = {}
        self._open = None
        self._ring = deque()
        self._entered = 0
        self._left = 0
        self._counter_date = None

        self.zones = ZoneTracker(cfg.zones_for(source.id), cooldown=max(10.0, cfg.events.cooldown_sec))
        self.privacy = PrivacyBlur(cfg.privacy)
        self.heatmap = Heatmap()
        self._last_purge = time.time()
        self._last_active = time.time()
        self._prev_gray = None
        self._fall_since = {}
        self._fall_alerted = {}
        self._static_obj = {}
        self.pose = None
        self._jobs = jobs

        self.alpr = AlprReader(cfg.alpr)
        self._alpr_queue = BoundedQueue(maxsize=64)
        self._alpr_thread = None
        self._plate_read = {}
        self._plate_attempt = {}
        self._face_queue = BoundedQueue(maxsize=64)
        self._face_thread = None
        self._last_face_ts = time.time()
        self._reid_queue = BoundedQueue(maxsize=64)
        self._reid_thread = None
        self._appearance_attempt = {}

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, name=f"pipeline-{self.source.id}", daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._close_open_event()

    @property
    def running(self):
        return self._running

    def health(self) -> str:
        s = self.stats
        if s["status"] == "error":
            return "offline"
        if s["status"] == "running":
            lt = s.get("last_frame_ts")
            if lt is not None and time.time() - lt > 30:
                return "stalled"
            return "healthy"
        return "stopped"

    def _run(self):
        import cv2

        cfg = self.cfg
        detector = self.detector
        detector.warmup(cfg.detection.imgsz)

        pre_frames = max(1, int(cfg.events.clip_pre_sec * 30))
        self._ring = deque(maxlen=pre_frames)

        cap = self._open_capture()
        if cap is None:
            with self._lock:
                self.stats["status"] = "error"
                self.stats["error"] = "could not open source"
            return

        src_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        fps_alpha = 0.1
        smoothed_fps = src_fps
        frame_idx = 0
        last_t = time.perf_counter()
        frame_t0 = time.perf_counter()

        with self._lock:
            self.stats["status"] = "running"

        while self._running:
            ok, frame = cap.read()
            if not ok:
                if self._is_file():
                    if self.source.loop:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    break
                time.sleep(1.0)
                cap.release()
                cap = self._open_capture()
                if cap is None:
                    time.sleep(2.0)
                continue

            frame_idx += 1
            ts = now_ts()
            today = time.strftime("%Y-%m-%d")
            if self._counter_date != today:
                self._counter_date = today
                self._entered = 0
                self._left = 0
            frame = resize_frame(frame, cfg.events.clip_max_width)

            motion = self._motion_score(frame)
            if self.source.fast:
                motion_idle = False
                eff_imgsz = 320
                eff_stride = max(cfg.detection.frame_stride, 3)
            else:
                motion_idle = cfg.detection.motion_enabled and motion < cfg.detection.motion_threshold
                idle = (ts - self._last_active) > 3.0
                eff_imgsz = 320 if idle else cfg.detection.imgsz
                eff_stride = max(cfg.detection.frame_stride, 8) if idle else cfg.detection.frame_stride
            if motion_idle:
                self._last_dets = []
            elif frame_idx % max(1, eff_stride) == 0:
                try:
                    self._last_dets = detector.track(frame, imgsz=eff_imgsz)
                    if self._last_dets:
                        self._last_active = ts
                except Exception as exc:
                    log.warning("detection error: %s", exc)
            dets = self._last_dets

            self._ring.append((ts, frame, dets))
            self._update_tracks(dets, ts)
            self._handle_events(frame, ts, src_fps)

            for ze in self.zones.update(dets, ts, frame.shape[1], frame.shape[0]):
                self._record_instant_event(frame, ts, ze)
            self._detect_falls(dets, ts, frame)
            self._detect_abandoned(dets, ts, frame)
            self._maybe_enqueue_alpr(dets, ts, frame)
            self._maybe_enqueue_face(dets, ts, frame)
            self._maybe_enqueue_reid(dets, ts, frame)
            for d in dets:
                if d.label == "person":
                    x1, y1, x2, y2 = d.xyxy
                    self.heatmap.add_point(
                        (x1 + x2) / 2 / max(1, frame.shape[1]),
                        (y1 + y2) / 2 / max(1, frame.shape[0]),
                    )
            self._maybe_purge(ts)

            annotated = draw_detections(self.privacy.apply(frame, dets), dets)
            if self._open is not None:
                annotated = self._draw_banner(annotated, "REC  " + ", ".join(sorted(self._open.objects)))
            annotated = draw_timestamp(annotated)
            with self._lock:
                self.latest_frame = annotated

            t = time.perf_counter()
            dt = t - last_t
            last_t = t
            if dt > 0:
                smoothed_fps = smoothed_fps * (1 - fps_alpha) + (1.0 / dt) * fps_alpha
            with self._lock:
                self.stats["fps"] = round(smoothed_fps, 1)
                self.stats["frames"] = frame_idx
                self.stats["active_objects"] = sorted({d.label for d in dets})
                counts = {}
                for d in dets:
                    counts[d.label] = counts.get(d.label, 0) + 1
                self.stats["object_counts"] = counts
                self.stats["entered"] = self._entered
                self.stats["left"] = self._left
                self.stats["zones"] = self.zones.snapshot()
                self.stats["last_frame_ts"] = ts
                self.stats["error"] = ""

            if self._is_file() and not self.source.fast:
                elapsed = time.perf_counter() - frame_t0
                target = 1.0 / max(1.0, src_fps)
                if elapsed < target:
                    time.sleep(target - elapsed)
            frame_t0 = time.perf_counter()

        cap.release()
        self._close_open_event()
        self._running = False
        with self._lock:
            self.stats["status"] = "stopped"

    def _open_capture(self):
        import cv2
        from .config import ROOT

        uri = str(self.source.uri)
        if uri.isdigit():
            target = int(uri)
        elif uri.startswith(("rtsp://", "rtmp://", "http://", "https://")):
            target = uri
        else:
            p = Path(uri)
            target = str(p if p.is_absolute() else ROOT / p)
        cap = cv2.VideoCapture(target)
        if not cap.isOpened() and not uri.isdigit():
            cap.release()
            cap = cv2.VideoCapture(target, cv2.CAP_FFMPEG)
        return cap if cap.isOpened() else None

    def _is_file(self):
        u = str(self.source.uri)
        return not u.isdigit() and not u.startswith(("rtsp://", "rtmp://", "http://", "https://"))

    def _motion_score(self, frame) -> float:
        import cv2

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray, (320, 240), interpolation=cv2.INTER_AREA)
        if self._prev_gray is None:
            self._prev_gray = small
            return 1.0
        diff = cv2.absdiff(small, self._prev_gray)
        _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
        score = float(np.count_nonzero(thresh)) / thresh.size
        self._prev_gray = small
        return score

    def _update_tracks(self, dets, ts):
        seen = set()
        for d in dets:
            if d.track_id is None:
                continue
            seen.add(d.track_id)
            meta = self._track_meta.get(d.track_id)
            if meta is None:
                self._entered += 1
                self._track_meta[d.track_id] = {
                    "label": d.label, "first_seen": ts, "last_seen": ts,
                    "max_conf": d.conf, "last_event_ts": 0.0,
                }
            else:
                meta["last_seen"] = ts
                meta["max_conf"] = max(meta["max_conf"], d.conf)
                meta["label"] = d.label
        for tid in list(self._track_meta):
            if tid not in seen and ts - self._track_meta[tid]["last_seen"] > TRACK_TIMEOUT_SEC:
                self._track_meta.pop(tid, None)
                self._left += 1

    def _trigger_present(self, dets):
        trig = set(self.cfg.events.trigger_classes)
        out = {}
        for d in dets:
            if d.track_id is not None and d.label in trig:
                out[d.track_id] = d.label
        return out

    def _handle_events(self, frame, ts, src_fps):
        cfg = self.cfg.events
        present = self._trigger_present(self._last_dets)

        if self._open is None:
            for tid, label in present.items():
                meta = self._track_meta.get(tid)
                if meta is None:
                    continue
                if (ts - meta["first_seen"]) < cfg.min_presence_sec:
                    continue
                if (ts - meta.get("last_event_ts", 0.0)) < cfg.cooldown_sec:
                    continue
                self._open_event(ts, present, src_fps)
                break
        else:
            ev = self._open
            if present:
                ev.last_trigger_seen = ts
                ev.thumb_frame = frame.copy()
                for tid, label in present.items():
                    ev.track_ids.add(tid)
                    ev.objects.add(label)
                    meta = self._track_meta.get(tid)
                    if meta:
                        ev.max_conf = max(ev.max_conf, meta["max_conf"])
            ev.writer.write(self.privacy.apply(frame, self._last_dets))
            ev.frames += 1
            if (ts - ev.last_trigger_seen) >= cfg.clip_post_sec or (ts - ev.start_ts) >= MAX_CLIP_SEC:
                self._finalize_event(ts)

    def _open_event(self, ts, present, src_fps):
        cfg = self.cfg.events
        event_id = self.store.add_event({
            "camera_id": self.source.id, "camera_name": self.source.name,
            "start_ts": ts, "end_ts": None, "duration": None,
            "objects": sorted(set(present.values())),
            "top_object": self._top_object(present.values()),
            "track_ids": sorted(present.keys()), "max_conf": 0.0,
            "event_type": "detection", "clip_path": None, "thumb_path": None,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        })
        frame = self.latest_frame
        if frame is None and self._ring:
            frame = self._ring[-1][1]
        if frame is None:
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
        h, w = frame.shape[:2]
        clip_path = self.cfg.clips_dir / f"{self.source.id}_{int(ts*1000)}.mp4"
        writer, actual_path = self._make_writer(str(clip_path), w, h, src_fps)
        if writer is None:
            log.error("could not create clip writer")
            return
        for rts, rframe, rdets in self._ring:
            if rts >= ts - cfg.clip_pre_sec:
                writer.write(self.privacy.apply(rframe, rdets))

        self._open = _OpenEvent(event_id, ts, writer, frame.copy(), src_fps, str(actual_path))
        self._open.track_ids = set(present.keys())
        self._open.objects = set(present.values())
        self._open.last_trigger_seen = ts
        with self._lock:
            self.stats["last_event"] = {"id": event_id, "objects": sorted(self._open.objects)}

    def _finalize_event(self, ts):
        ev = self._open
        if ev is None:
            return
        ev.writer.release()
        duration = max(0.0, ts - ev.start_ts)
        clip_path = Path(ev.clip_path)
        thumb_path = save_thumbnail(
            self.privacy.apply(ev.thumb_frame, self._last_dets),
            self.cfg.thumbs_dir / f"{self.source.id}_{int(ev.start_ts*1000)}.jpg",
        )
        objects = sorted(ev.objects)
        self.store.update_event(
            ev.event_id, end_ts=ts, duration=round(duration, 2), objects=objects,
            top_object=self._top_object(objects), track_ids=sorted(ev.track_ids),
            max_conf=round(ev.max_conf, 3), clip_path=str(clip_path), thumb_path=str(thumb_path),
        )
        for tid in ev.track_ids:
            if tid in self._track_meta:
                self._track_meta[tid]["last_event_ts"] = ts
        if any(o in ("car", "truck", "bus", "motorcycle") for o in objects):
            rp = self.store.recent_plate(self.source.id, ev.start_ts - 5.0, ts + 5.0)
            if rp:
                self.store.update_event(ev.event_id, plate=rp["plate"])
        self._open = None
        log.info("event %s finalized: %s (%.1fs)", ev.event_id, objects, duration)
        self._spawn_post(ev.event_id, clip_path)

    def _record_instant_event(self, frame, ts, payload):
        etype = payload["type"]
        clip_path = self.cfg.clips_dir / f"{self.source.id}_{int(ts*1000)}_{etype}.mp4"
        writer, actual = self._make_writer(str(clip_path), frame.shape[1], frame.shape[0], self.cfg.events.clip_fps)
        if writer is not None:
            for rts, rframe, rdets in self._ring:
                if rts >= ts - self.cfg.events.clip_pre_sec:
                    writer.write(self.privacy.apply(rframe, rdets))
            writer.release()
        thumb = save_thumbnail(
            self.privacy.apply(frame, self._last_dets),
            self.cfg.thumbs_dir / f"{self.source.id}_{int(ts*1000)}_{etype}.jpg",
        )
        objs = payload.get("objects") or []
        eid = self.store.add_event({
            "camera_id": self.source.id, "camera_name": self.source.name,
            "start_ts": ts, "end_ts": ts, "duration": 0.0, "objects": objs,
            "top_object": objs[0] if objs else None, "track_ids": [], "max_conf": 0.0,
            "event_type": etype, "summary": payload.get("note", ""),
            "clip_path": str(actual) if writer is not None else None,
            "thumb_path": str(thumb),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        })
        log.info("instant event %s: %s", etype, payload.get("note"))
        self._spawn_post(eid, Path(actual) if writer is not None else None)
        return eid

    def _ensure_pose(self):
        if self.pose is not None:
            return
        try:
            from .pose import PoseDetector

            self.pose = PoseDetector(self.cfg.events.fall_pose_model)
        except Exception as exc:
            log.warning("pose model unavailable, using bbox fall detection: %s", exc)
            self.pose = False

    def _detect_falls(self, dets, ts, frame):
        cfg = self.cfg.events
        for d in dets:
            if d.label != "person" or d.track_id is None:
                continue
            x1, y1, x2, y2 = d.xyxy
            h = y2 - y1
            w = x2 - x1
            if h <= 0:
                continue
            fallen = False
            if w / h >= 0.7:
                self._ensure_pose()
                if self.pose:
                    try:
                        crop = frame[int(y1):int(y2), int(x1):int(x2)]
                        angle = self.pose.torso_angle(crop)
                        if angle is not None:
                            fallen = angle >= cfg.fall_angle_deg
                    except Exception as exc:
                        log.warning("pose fall check failed: %s", exc)
                if not fallen:
                    fallen = (w / h) >= cfg.fall_bbox_ratio
            if fallen:
                if d.track_id not in self._fall_since:
                    self._fall_since[d.track_id] = ts
                elif ts - self._fall_since[d.track_id] >= cfg.fall_min_sec:
                    if ts - self._fall_alerted.get(d.track_id, 0.0) >= cfg.cooldown_sec:
                        self._fall_alerted[d.track_id] = ts
                        self._record_instant_event(frame, ts, {
                            "type": "fall", "zone": "",
                            "note": "Possible fall detected (person down)",
                            "objects": ["person"],
                        })
            else:
                self._fall_since.pop(d.track_id, None)

    def _detect_abandoned(self, dets, ts, frame):
        cfg = self.cfg.events
        persons = [d for d in dets if d.label == "person"]
        for d in dets:
            if d.label not in cfg.abandoned_classes or d.track_id is None:
                continue
            x1, y1, x2, y2 = d.xyxy
            center = ((x1 + x2) / 2, (y1 + y2) / 2)
            owner_nearby = any(
                self._dist(center, ((p.xyxy[0] + p.xyxy[2]) / 2, (p.xyxy[1] + p.xyxy[3]) / 2)) < cfg.abandoned_owner_radius_px
                for p in persons
            )
            st = self._static_obj.get(d.track_id)
            if st is None:
                self._static_obj[d.track_id] = {"center": center, "static_since": 0.0, "alerted": 0.0}
                continue
            moved = self._dist(center, st["center"]) > STATIC_MOVE_PX
            st["center"] = center
            if moved or owner_nearby:
                st["static_since"] = 0.0
            else:
                if st["static_since"] == 0.0:
                    st["static_since"] = ts
                elif ts - st["static_since"] >= cfg.abandoned_sec and ts - st.get("alerted", 0.0) >= cfg.cooldown_sec:
                    st["alerted"] = ts
                    self._record_instant_event(frame, ts, {
                        "type": "abandoned", "zone": "",
                        "note": f"Unattended {d.label} detected",
                        "objects": [d.label],
                    })

    def _maybe_enqueue_alpr(self, dets, ts, frame):
        cfg = self.cfg.alpr
        if not cfg.enabled:
            return
        vehicle_classes = ("car", "truck", "bus", "motorcycle")
        parking_zones = [z for z in self.cfg.zones_for(self.source.id) if z.parking]
        for d in dets:
            if d.label not in vehicle_classes or d.track_id is None:
                continue
            if d.track_id in self._plate_read:
                continue
            if ts - self._plate_attempt.get(d.track_id, 0.0) < cfg.throttle_sec:
                continue
            x1, y1, x2, y2 = d.xyxy
            if cfg.zones_only and parking_zones:
                cx = (x1 + x2) / 2 / max(1, frame.shape[1])
                cy = y2 / max(1, frame.shape[0])
                if not any(point_in_polygon(cx, cy, z.points) for z in parking_zones):
                    continue
            pad = 0.12
            w = x2 - x1
            h = y2 - y1
            x1 = max(0, int(x1 - pad * w))
            y1 = max(0, int(y1 - pad * h))
            x2 = min(frame.shape[1], int(x2 + pad * w))
            y2 = min(frame.shape[0], int(y2 + pad * h))
            if x2 <= x1 or y2 <= y1:
                continue
            crop = frame[y1:y2, x1:x2].copy()
            self._plate_attempt[d.track_id] = ts
            self._alpr_queue.put((crop, d.track_id, ts, d.label))
            self._start_alpr_worker()

    def _start_alpr_worker(self):
        if self._alpr_thread is None or not self._alpr_thread.is_alive():
            self._alpr_thread = threading.Thread(target=self._alpr_worker, name="alpr-" + self.source.id, daemon=True)
            self._alpr_thread.start()

    def _alpr_worker(self):
        while self._running:
            try:
                crop, track_id, ts, label = self._alpr_queue.get(timeout=1.0)
            except queue.Empty:
                continue
            try:
                plate, conf, plate_crop = self.alpr.read_plate(crop)
            except Exception as exc:
                log.warning("ALPR error: %s", exc)
                continue
            if not plate:
                continue
            self._plate_read[track_id] = plate
            crop_path = None
            if self.cfg.alpr.save_crop and plate_crop is not None:
                try:
                    fn = "plate_" + self.source.id + "_" + str(int(ts * 1000)) + "_" + str(track_id) + ".jpg"
                    crop_path = save_thumbnail(plate_crop, self.cfg.thumbs_dir / fn)
                except Exception as exc:
                    log.warning("plate crop save failed: %s", exc)
            self.store.insert_plate({
                "camera_id": self.source.id,
                "camera_name": self.source.name,
                "plate": plate,
                "confidence": round(float(conf), 3),
                "crop_path": str(crop_path) if crop_path else None,
                "ts": ts,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            })
            log.info("plate read: %s (%.2f)", plate, conf)

    def _maybe_enqueue_face(self, dets, ts, frame):
        cfg = self.cfg.face
        if not cfg.enabled or self.face_engine is None:
            return
        if not any(d.label == "person" for d in dets):
            return
        if ts - self._last_face_ts < cfg.throttle_sec:
            return
        self._last_face_ts = ts
        self._face_queue.put((frame.copy(), ts))
        self._start_face_worker()

    def _start_face_worker(self):
        if self._face_thread is None or not self._face_thread.is_alive():
            self._face_thread = threading.Thread(target=self._face_worker, name="face-" + self.source.id, daemon=True)
            self._face_thread.start()

    def _face_worker(self):
        cfg = self.cfg.face
        while self._running:
            try:
                frame, ts = self._face_queue.get(timeout=1.0)
            except queue.Empty:
                continue
            try:
                faces = self.face_engine.detect_and_embed(frame)
            except Exception as exc:
                log.warning("face recognition error: %s", exc)
                continue
            if not faces:
                continue
            known = self.store.list_faces()
            for f in faces:
                emb = f["embedding"]
                best_id = None
                best_name = "unknown"
                best_conf = 0.0
                for k in known:
                    s = FaceEngine.cosine(emb, k["embedding"])
                    if s > best_conf:
                        best_conf = s
                        best_id = k["id"]
                        best_name = k["name"]
                if best_conf < cfg.min_conf:
                    best_id = None
                    best_name = "unknown"
                    best_conf = 0.0
                thumb = None
                if cfg.save_crop:
                    try:
                        x1, y1, x2, y2 = [int(v) for v in f["box"]]
                        crop = frame[max(0, y1):y2, max(0, x1):x2]
                        if crop.size:
                            fn = "face_" + self.source.id + "_" + str(int(ts * 1000)) + "_" + str(int(best_conf * 100)) + ".jpg"
                            thumb = save_thumbnail(crop, self.cfg.thumbs_dir / fn)
                    except Exception as exc:
                        log.warning("face crop save failed: %s", exc)
                self.store.add_face_match({
                    "camera_id": self.source.id,
                    "camera_name": self.source.name,
                    "face_id": best_id,
                    "name": best_name,
                    "confidence": round(float(best_conf), 3),
                    "embedding": emb,
                    "thumb_path": str(thumb) if thumb else None,
                    "ts": ts,
                })
                if best_name != "unknown":
                    self._anchor_identity(frame, f["box"], best_id, best_name, ts)
                log.info("face: %s (%.2f)", best_name, best_conf)

    def _maybe_enqueue_reid(self, dets, ts, frame):
        cfg = self.cfg.reid
        if not cfg.enabled or self.reid_engine is None:
            return
        for d in dets:
            if d.label != "person" or d.track_id is None:
                continue
            if ts - self._appearance_attempt.get(d.track_id, 0.0) < cfg.throttle_sec:
                continue
            self._appearance_attempt[d.track_id] = ts
            x1, y1, x2, y2 = [int(v) for v in d.xyxy]
            crop = frame[max(0, y1):y2, max(0, x1):x2]
            if crop.size == 0:
                continue
            self._reid_queue.put((crop.copy(), d.track_id, ts))
            self._start_reid_worker()

    def _start_reid_worker(self):
        if self._reid_thread is None or not self._reid_thread.is_alive():
            self._reid_thread = threading.Thread(target=self._reid_worker, name="reid-" + self.source.id, daemon=True)
            self._reid_thread.start()

    def _reid_worker(self):
        cfg = self.cfg.reid
        while self._running:
            try:
                crop, track_id, ts = self._reid_queue.get(timeout=1.0)
            except queue.Empty:
                continue
            try:
                emb = self.reid_engine.embed(crop)
            except Exception as exc:
                log.warning("reid embed error: %s", exc)
                continue
            if emb is None:
                continue
            thumb = None
            if cfg.save_crop:
                try:
                    fn = "app_" + self.source.id + "_" + str(int(ts * 1000)) + "_" + str(track_id) + ".jpg"
                    thumb = save_thumbnail(crop, self.cfg.thumbs_dir / fn)
                except Exception as exc:
                    log.warning("appearance crop save failed: %s", exc)
            self.store.add_appearance(self.source.id, self.source.name, track_id, emb, str(thumb) if thumb else None, ts)
            for ident in self.store.list_identities():
                gallery = ident["embedding"] or []
                best = max((ReidEngine.cosine(emb, g) for g in gallery), default=0.0)
                if best >= cfg.min_conf:
                    self.store.add_sighting(ident["id"], self.source.id, self.source.name, round(float(best), 3), str(thumb) if thumb else None, ts)
                    log.info("sighting: %s on %s (%.2f)", ident["name"], self.source.id, best)

    def _anchor_identity(self, frame, face_box, face_id, name, ts):
        if self.reid_engine is None or face_id is None:
            return
        try:
            fx1, fy1, fx2, fy2 = [int(v) for v in face_box]
            fw = fx2 - fx1
            fh = fy2 - fy1
            x1 = max(0, fx1 - fw)
            x2 = min(frame.shape[1], fx2 + fw)
            y1 = max(0, fy1 - fh)
            y2 = min(frame.shape[0], fy2 + 5 * fh)
            crop = frame[y1:y2, x1:x2]
            if crop.size == 0:
                return
            emb = self.reid_engine.embed(crop)
            if emb is None:
                return
            existing = None
            for i in self.store.list_identities():
                if i.get("face_id") == face_id:
                    existing = i
                    break
            if existing is None:
                thumb = None
                try:
                    thumb = save_thumbnail(crop, self.cfg.thumbs_dir / ("ident_" + name + ".jpg"))
                except Exception:
                    pass
                self.store.add_identity(name, face_id, emb, str(thumb) if thumb else None)
                log.info("identity anchored: %s", name)
            else:
                self.store.add_identity_embedding(existing["id"], emb)
        except Exception as exc:
            log.warning("identity anchoring failed: %s", exc)

    def _maybe_purge(self, ts):
        if self.cfg.retention.retention_days <= 0:
            return
        interval = self.cfg.retention.purge_interval_sec
        if interval <= 0 or ts - self._last_purge < interval:
            return
        self._last_purge = ts
        try:
            retention_purge(self.cfg, self.store)
        except Exception as exc:
            log.warning("retention purge failed: %s", exc)

    def _spawn_post(self, event_id, clip_path):
        if self._jobs is not None:
            self._jobs.submit(self._post_process, event_id, clip_path)
        else:
            threading.Thread(target=self._post_process, args=(event_id, clip_path), daemon=True).start()

    def _post_process(self, event_id, clip_path):
        event = self.store.get_event(event_id)
        if event is None:
            return
        summary = event.get("summary")
        if not summary and clip_path is not None:
            keyframes = extract_keyframes(
                clip_path, self.cfg.thumbs_dir / f"{self.source.id}_{int(event['start_ts']*1000)}", n=3
            )
            if not keyframes and event.get("thumb_path"):
                keyframes = [event["thumb_path"]]
            summary = self.summarizer.summarize(event, keyframes)
            if summary:
                self.store.update_event(event_id, summary=summary, summary_model=self.summarizer.cfg.model)
                event["summary"] = summary
        if self.notifier.send_event(event, summary):
            self.store.mark_notified(event_id)
        if self.webhook is not None:
            self.webhook.send(event)

    def _close_open_event(self):
        if self._open is not None:
            self._finalize_event(now_ts())

    @staticmethod
    def _dist(a, b):
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

    @staticmethod
    def _top_object(values):
        vals = list(values)
        if not vals:
            return None
        return max(set(vals), key=vals.count) if len(vals) > 1 else vals[0]

    @staticmethod
    def _make_writer(path, w, h, fps):
        import cv2

        fps = max(2.0, min(float(fps), 60.0))
        for codec, ext in (("mp4v", ".mp4"), ("XVID", ".avi"), ("MJPG", ".avi")):
            p = Path(path)
            if p.suffix != ext:
                p = p.with_suffix(ext)
            writer = cv2.VideoWriter(str(p), cv2.VideoWriter_fourcc(*codec), fps, (w, h))
            if writer.isOpened():
                return writer, p
        return None, Path(path)

    @staticmethod
    def _draw_banner(frame, text):
        import cv2

        img = frame.copy()
        h, w = img.shape[:2]
        cv2.rectangle(img, (0, 0), (min(360, w), 34), (0, 0, 220), -1)
        cv2.putText(img, text[:40], (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
        return img


class PipelineManager:
    def __init__(self, cfg):
        self.cfg = cfg
        cfg.ensure_dirs()
        self.store = EventStore(db_path=cfg.db_path, database_url=getattr(cfg, "database_url", "") or None)
        self.detector = Detector(cfg.detection)
        self.notifier = Notifier(cfg.notify)
        self.summarizer = VLMSummarizer(cfg.vlm)
        self.webhook = Webhook(cfg.webhook)
        self.face_engine = FaceEngine(cfg.face)
        self.reid_engine = ReidEngine(cfg.reid)
        self._desired = set()
        self._watchdog = None
        self._last_report_date = None
        if cfg.report.enabled:
            threading.Thread(target=self._report_loop, daemon=True).start()
        self._camera_health_state = {}
        threading.Thread(target=self._monitor_loop, daemon=True).start()
        try:
            retention_purge(cfg, self.store)
        except Exception:
            pass
        self.jobs = JobPool(workers=getattr(cfg, "workers", 2))
        self.pipelines = {
            s.id: CameraPipeline(s, cfg, self.store, self.detector, self.notifier, self.summarizer, self.webhook, self.face_engine, self.reid_engine, jobs=self.jobs)
            for s in cfg.sources
        }

    def start(self, source_id):
        if source_id in self.pipelines:
            self._desired.add(source_id)
            self.pipelines[source_id].start()
            self._ensure_watchdog()

    def stop(self, source_id):
        self._desired.discard(source_id)
        if source_id in self.pipelines:
            self.pipelines[source_id].stop()

    def start_all(self):
        for sid in self.pipelines:
            self.start(sid)

    def stop_all(self):
        for sid in list(self._desired):
            self.stop(sid)

    def add_source(self, source: SourceConfig) -> str:
        """Register a new source (e.g. an uploaded video) and return its id."""
        if source.id in self.pipelines:
            return source.id
        self.pipelines[source.id] = CameraPipeline(
            source, self.cfg, self.store, self.detector, self.notifier, self.summarizer, self.webhook,
            self.face_engine, self.reid_engine, jobs=self.jobs,
        )
        if not any(s.id == source.id for s in self.cfg.sources):
            self.cfg.sources.append(source)
        return source.id

    def remove_source(self, source_id: str) -> None:
        if source_id in self.pipelines:
            self._desired.discard(source_id)
            self.pipelines[source_id].stop()
            del self.pipelines[source_id]
        self.cfg.sources = [s for s in self.cfg.sources if s.id != source_id]

    def search(self, query, camera_id=None, limit=50):
        return SmartSearch(self.store, self.detector.names).run(query, limit=limit, camera_id=camera_id)

    def save_config(self, cfg=None):
        from .config import save_config as _save

        return _save(cfg or self.cfg)

    def occupancy(self) -> dict:
        """Count people and vehicles across all cameras (live)."""
        people = 0
        vehicles = 0
        entered = 0
        left = 0
        cameras = {}
        vehicle_classes = ("car", "truck", "bus", "motorcycle", "bicycle")
        for s in self.cfg.sources:
            p = self.pipelines.get(s.id)
            if p is None:
                continue
            counts = p.stats.get("object_counts", {}) or {}
            ppl = int(counts.get("person", 0))
            veh = sum(int(counts.get(k, 0)) for k in vehicle_classes)
            people += ppl
            vehicles += veh
            entered += int(p.stats.get("entered", 0))
            left += int(p.stats.get("left", 0))
            cameras[s.id] = {
                "name": s.name, "people": ppl, "vehicles": veh,
                "entered": int(p.stats.get("entered", 0)), "left": int(p.stats.get("left", 0)),
                "status": p.stats.get("status", "unknown"), "health": p.health(),
            }
        return {"people": people, "vehicles": vehicles, "entered": entered, "left": left, "cameras": cameras}

    def _report_loop(self):
        while True:
            time.sleep(300)
            try:
                if self._should_send_report():
                    self._send_report()
            except Exception as exc:
                log.warning("report scheduler error: %s", exc)

    def _should_send_report(self):
        from datetime import datetime

        now = datetime.now()
        if now.hour != self.cfg.report.hour:
            return False
        if self.cfg.report.interval == "weekly" and now.weekday() != 0:
            return False
        if self._last_report_date == now.date():
            return False
        self._last_report_date = now.date()
        return True

    def _send_report(self):
        from .analytics import build_report

        since = time.time() - (86400 if self.cfg.report.interval == "daily" else 7 * 86400)
        rep = build_report(self.store, since, self.cfg.report.interval)
        if self.cfg.report.notify:
            self.notifier.send_report("SmartCam " + self.cfg.report.interval + " report", rep)
        log.info("report generated (%d chars)", len(rep))
        return rep

    def _monitor_loop(self):
        while True:
            time.sleep(30)
            try:
                self._check_escalations()
                self._check_camera_health()
                self._sample_occupancy()
            except Exception as exc:
                log.warning("monitor error: %s", exc)

    def _sample_occupancy(self):
        o = self.occupancy()
        if o["people"] > 0 or o["vehicles"] > 0:
            self.store.add_occupancy_sample(time.time(), o["people"], o["vehicles"])

    def _check_escalations(self):
        sec = self.cfg.events.escalation_sec
        if sec <= 0:
            return
        cutoff = time.time() - sec
        for ev in self.store.list_open_alerts(limit=200):
            if ev.get("acknowledged") or ev.get("escalated"):
                continue
            if (ev.get("start_ts") or 0) < cutoff:
                self.store.escalate(ev["id"])
                self.notifier.send_event(ev, "ESCALATED: unacknowledged alert")
                log.info("escalated event %s", ev["id"])

    def _check_camera_health(self):
        for s in self.cfg.sources:
            p = self.pipelines.get(s.id)
            if p is None:
                continue
            h = p.health()
            prev = self._camera_health_state.get(s.id)
            if prev is not None and prev != h and h in ("offline", "stalled"):
                self.notifier.send_alert("Camera " + s.name + " " + h, "Camera " + s.name + " is now " + h)
                log.warning("camera %s is %s", s.id, h)
            self._camera_health_state[s.id] = h

    def _ensure_watchdog(self):
        if self._watchdog is None or not self._watchdog.is_alive():
            self._watchdog = threading.Thread(target=self._watchdog_loop, daemon=True)
            self._watchdog.start()

    def _watchdog_loop(self):
        while True:
            time.sleep(15)
            for sid in list(self._desired):
                p = self.pipelines.get(sid)
                if p is None or not p._running:
                    continue
                if p._thread is not None and not p._thread.is_alive():
                    log.warning("pipeline %s thread died; restarting", sid)
                    p.start()

