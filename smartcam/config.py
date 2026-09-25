"""Configuration for SmartCam.

Configuration is loaded from a JSON file (config.json by default, or the
SMART_CAM_CONFIG env var). Missing keys fall back to built-in defaults.
Secrets (API keys, notification URLs/topics) can also be provided via
environment variables so they never touch disk.
"""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

log = logging.getLogger("smartcam.config")


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into a copy of *base* (dicts only)."""
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


@dataclass
class SourceConfig:
    id: str = "camera-1"
    name: str = "Camera 1"
    # "0" = webcam, "rtsp://...", "http://...", or a local file path.
    uri: str = "0"
    enabled: bool = True
    # Loop file sources when they reach EOF. False = single pass (assessment).
    loop: bool = True
    # Fast mode: lower resolution + higher stride + no throttle (for imports).
    fast: bool = False


@dataclass
class DetectionConfig:
    model: str = "yolov8n.onnx"
    # Compute device for the model: cpu | cuda | mps | auto. Falls back to cpu.
    device: str = "cpu"
    imgsz: int = 640
    conf: float = 0.35
    iou: float = 0.45
    tracker: str = "bytetrack.yaml"
    # Process every Nth frame (raise on slow CPU machines).
    frame_stride: int = 2
    # Optional whitelist of COCO class indices; empty = all classes.
    classes: list[int] = field(default_factory=list)
    # Motion gating: skip detection when the scene is still.
    motion_enabled: bool = True
    # Fraction of changed pixels that counts as "motion" (0..1).
    motion_threshold: float = 0.005


@dataclass
class EventConfig:
    # Objects whose presence triggers a standard "detection" event.
    trigger_classes: list[str] = field(
        default_factory=lambda: ["person", "car", "truck", "bus", "motorcycle", "bicycle"]
    )
    # Minimum time an object must be present before an event fires.
    min_presence_sec: float = 1.0
    # Minimum gap between consecutive events from the same track.
    cooldown_sec: float = 15.0
    # Clip length around an event.
    clip_pre_sec: float = 2.0
    clip_post_sec: float = 4.0
    clip_fps: float = 15.0
    clip_max_width: int = 1280
    # Fall detection: a person whose box width/height exceeds this ratio and
    # stays that way for fall_min_sec is flagged as a fall.
    fall_bbox_ratio: float = 1.15
    fall_min_sec: float = 2.0
    # Pose-based fall detection (more accurate than the box-ratio heuristic).
    fall_pose_model: str = "yolov8n-pose.pt"
    fall_angle_deg: float = 55.0
    # Auto-escalate unacknowledged events after this many seconds (0 = off).
    escalation_sec: float = 300.0
    # Abandoned object: a static object with no owner within owner_radius_px
    # for abandoned_sec is flagged as abandoned baggage.
    abandoned_sec: float = 30.0
    abandoned_owner_radius_px: float = 220.0
    abandoned_classes: list[str] = field(
        default_factory=lambda: ["suitcase", "handbag", "backpack", "umbrella"]
    )


@dataclass
class ZoneConfig:
    id: str = "zone-1"
    name: str = "Zone 1"
    # Optional source id this zone applies to ("" = all sources).
    source_id: str = ""
    # Polygon as NORMALIZED coordinates [[x,y],...] relative to frame (0..1).
    points: list[list[float]] = field(default_factory=list)
    # Classes that count toward this zone's rules (empty = person only).
    classes: list[str] = field(default_factory=lambda: ["person"])
    # Queue/crowd: alert when count of matching objects reaches max_occupancy.
    max_occupancy: int | None = None
    # Loitering: alert when a matching object stays in the zone >= loiter_sec.
    loiter_sec: float | None = None
    # Restricted zone: alert on ANY entry outside the allowed window.
    restricted: bool = False
    # Allowed window "HH:MM-HH:MM" (e.g. "06:00-22:00"). Empty = always allowed.
    allowed_window: str = ""
    # Parking zone: count vehicles against capacity (metric + full alert).
    parking: bool = False
    capacity: int | None = None


@dataclass
class PrivacyConfig:
    # Blur faces (or whole bodies) in the live view and recorded clips.
    blur_enabled: bool = False
    # "face" blurs detected faces; "body" blurs whole person boxes.
    blur_mode: str = "face"
    # Encrypt clip/thumbnail files at rest (Fernet). See smartcam.crypto.
    encrypt_files: bool = False
    encryption_key: str = ""


@dataclass
class RetentionConfig:
    # Auto-delete clips/thumbnails/records older than this many days. 0 = keep forever.
    retention_days: int = 30
    # Run the purge this often (seconds). 0 = only at startup.
    purge_interval_sec: int = 3600


@dataclass
class StorageConfig:
    # "local" (default) or "s3" (any S3-compatible: AWS S3, MinIO, R2, B2).
    provider: str = "local"
    bucket: str = ""
    endpoint_url: str = ""   # e.g. https://<account>.r2.cloudflarestorage.com or http://localhost:9000
    region: str = ""
    access_key: str = ""     # env: SMART_CAM_S3_ACCESS_KEY
    secret_key: str = ""     # env: SMART_CAM_S3_SECRET_KEY
    prefix: str = ""         # optional object-key prefix


@dataclass
class AuthUser:
    username: str = "admin"
    # sha256 hex digest of the password (see hash_password).
    password_hash: str = ""
    role: str = "admin"  # "admin" | "security" | "manager" | "viewer"


@dataclass
class AuthConfig:
    enabled: bool = False
    users: list[AuthUser] = field(default_factory=list)


@dataclass
class WebhookConfig:
    enabled: bool = False
    # POST JSON event payloads to this URL.
    url: str = ""
    timeout_sec: float = 10.0


@dataclass
class ReportConfig:
    enabled: bool = False
    # "daily" | "weekly"
    interval: str = "daily"
    # If provided, the report is also sent via the notifier.
    notify: bool = False
    # Hour of day (0-23) to generate/send the report.
    hour: int = 6


@dataclass
class AlprConfig:
    enabled: bool = False
    # Only run ALPR on vehicles inside parking/alpr zones.
    zones_only: bool = True
    # Minimum OCR confidence to accept a read (0-1).
    min_conf: float = 0.4
    # Seconds between ALPR attempts on the same vehicle track.
    throttle_sec: float = 5.0
    # Save the cropped plate image.
    save_crop: bool = True
    # EasyOCR languages, comma-separated.
    languages: str = "en"
    # Optional dedicated YOLO license-plate model (empty = vehicle-crop heuristic).
    plate_model: str = ""


@dataclass
class FaceConfig:
    enabled: bool = False
    # deepface model: "Facenet" (128-d), "Facenet512", "SFace", "ArcFace", ...
    model_name: str = "Facenet"
    # deepface detector: "yolov8", "opencv", "retinaface", "mtcnn", ...
    detector_backend: str = "yolov8"
    # Cosine-similarity threshold for a match (0-1).
    min_conf: float = 0.4
    # Seconds between face-recognition attempts per face.
    throttle_sec: float = 5.0
    # Save face-crop thumbnails.
    save_crop: bool = True


@dataclass
class ReidConfig:
    enabled: bool = False
    # torchreid OSNet model (this is BoxMOT's ReID engine).
    model_name: str = "osnet_x0_25"
    # Cosine-similarity threshold to consider the same person (0-1).
    min_conf: float = 0.55
    # Seconds between appearance-embedding runs per tracked person.
    throttle_sec: float = 3.0
    save_crop: bool = True


@dataclass
class VLMSummarizerConfig:
    enabled: bool = True
    # "openai" (any OpenAI-compatible endpoint) | "ollama" (local).
    provider: str = "openai"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""  # env: SMART_CAM_OPENAI_API_KEY
    model: str = "gpt-4o-mini"
    max_keyframes: int = 3
    timeout_sec: int = 60


@dataclass
class NotifyConfig:
    enabled: bool = True
    # Apprise URL, e.g. "ntfy://mytopic", "ntfys://host/mytopic",
    # "pushover://user:token", "tgram://botToken/chatId", ...
    apprise_url: str = ""  # env: SMART_CAM_NOTIFY_URL
    # ntfy end-to-end encryption (optional).
    e2e_encrypt: bool = False
    ntfy_topic: str = ""  # env: SMART_CAM_NTFY_TOPIC
    ntfy_public_key: str = ""  # recipient's base64 X25519 public key (for E2E)
    ntfy_server: str = "https://ntfy.sh"


@dataclass
class WebRTCConfig:
    # Serve low-latency WebRTC live streams (requires aiortc on the server).
    enabled: bool = True
    # STUN server(s) for address discovery. Public Google STUN by default.
    stun_urls: list[str] = field(default_factory=lambda: ["stun:stun.l.google.com:19302"])
    # Optional TURN relay (needed for edge cameras behind symmetric NAT/firewalls).
    turn_url: str = ""           # e.g. "turn:turn.example.com:3478"
    turn_username: str = ""
    turn_credential: str = ""    # env: SMART_CAM_TURN_CREDENTIAL


@dataclass
class AppConfig:
    data_dir: Path = field(default_factory=lambda: ROOT / "data")
    sources: list[SourceConfig] = field(default_factory=lambda: [SourceConfig()])
    zones: list[ZoneConfig] = field(default_factory=list)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    events: EventConfig = field(default_factory=EventConfig)
    privacy: PrivacyConfig = field(default_factory=PrivacyConfig)
    retention: RetentionConfig = field(default_factory=RetentionConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)
    webhook: WebhookConfig = field(default_factory=WebhookConfig)
    report: ReportConfig = field(default_factory=ReportConfig)
    alpr: AlprConfig = field(default_factory=AlprConfig)
    face: FaceConfig = field(default_factory=FaceConfig)
    reid: ReidConfig = field(default_factory=ReidConfig)
    vlm: VLMSummarizerConfig = field(default_factory=VLMSummarizerConfig)
    notify: NotifyConfig = field(default_factory=NotifyConfig)
    webrtc: WebRTCConfig = field(default_factory=WebRTCConfig)
    # Background post-processing workers (VLM summaries, notifications, webhooks).
    workers: int = 2
    # Optional Postgres URL (env DATABASE_URL only; not persisted to config.json).
    database_url: str = ""

    @property
    def clips_dir(self) -> Path:
        return self.data_dir / "clips"

    @property
    def thumbs_dir(self) -> Path:
        return self.data_dir / "thumbs"

    @property
    def analytics_dir(self) -> Path:
        return self.data_dir / "analytics"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "events.db"

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.clips_dir, self.thumbs_dir, self.analytics_dir):
            d.mkdir(parents=True, exist_ok=True)

    def zones_for(self, source_id: str) -> list[ZoneConfig]:
        return [z for z in self.zones if not z.source_id or z.source_id == source_id]


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _source_to_dict(s: SourceConfig) -> dict[str, Any]:
    return {"id": s.id, "name": s.name, "uri": s.uri, "enabled": s.enabled, "loop": s.loop, "fast": s.fast}


def _source_from_dict(d: dict[str, Any]) -> SourceConfig:
    return SourceConfig(
        id=d.get("id", "camera-1"),
        name=d.get("name", "Camera 1"),
        uri=d.get("uri", "0"),
        enabled=bool(d.get("enabled", True)),
        loop=bool(d.get("loop", True)),
        fast=bool(d.get("fast", False)),
    )


def _zone_to_dict(z: ZoneConfig) -> dict[str, Any]:
    return {
        "id": z.id, "name": z.name, "source_id": z.source_id,
        "points": z.points, "classes": z.classes,
        "max_occupancy": z.max_occupancy, "loiter_sec": z.loiter_sec,
        "restricted": z.restricted, "allowed_window": z.allowed_window,
        "parking": z.parking, "capacity": z.capacity,
    }


def _zone_from_dict(d: dict[str, Any]) -> ZoneConfig:
    return ZoneConfig(
        id=d.get("id", "zone-1"),
        name=d.get("name", "Zone 1"),
        source_id=d.get("source_id", ""),
        points=d.get("points", []),
        classes=d.get("classes", ["person"]),
        max_occupancy=d.get("max_occupancy"),
        loiter_sec=d.get("loiter_sec"),
        restricted=bool(d.get("restricted", False)),
        allowed_window=d.get("allowed_window", ""),
        parking=bool(d.get("parking", False)),
        capacity=d.get("capacity"),
    )


def _apply_env_secrets(cfg: AppConfig) -> AppConfig:
    env = os.environ
    if env.get("SMART_CAM_OPENAI_API_KEY"):
        cfg.vlm.api_key = env["SMART_CAM_OPENAI_API_KEY"]
    if env.get("SMART_CAM_NOTIFY_URL"):
        cfg.notify.apprise_url = env["SMART_CAM_NOTIFY_URL"]
    if env.get("SMART_CAM_NTFY_TOPIC"):
        cfg.notify.ntfy_topic = env["SMART_CAM_NTFY_TOPIC"]
    if env.get("SMART_CAM_DATA_DIR"):
        cfg.data_dir = Path(env["SMART_CAM_DATA_DIR"])
    if env.get("SMART_CAM_S3_BUCKET"):
        cfg.storage.bucket = env["SMART_CAM_S3_BUCKET"]
    if env.get("SMART_CAM_S3_ENDPOINT"):
        cfg.storage.endpoint_url = env["SMART_CAM_S3_ENDPOINT"]
    if env.get("SMART_CAM_S3_ACCESS_KEY"):
        cfg.storage.access_key = env["SMART_CAM_S3_ACCESS_KEY"]
    if env.get("SMART_CAM_S3_SECRET_KEY"):
        cfg.storage.secret_key = env["SMART_CAM_S3_SECRET_KEY"]
    if env.get("SMART_CAM_TURN_URL"):
        cfg.webrtc.turn_url = env["SMART_CAM_TURN_URL"]
    if env.get("SMART_CAM_TURN_USERNAME"):
        cfg.webrtc.turn_username = env["SMART_CAM_TURN_USERNAME"]
    if env.get("SMART_CAM_TURN_CREDENTIAL"):
        cfg.webrtc.turn_credential = env["SMART_CAM_TURN_CREDENTIAL"]
    if env.get("DATABASE_URL"):
        cfg.database_url = env["DATABASE_URL"]
    return cfg


def load_config(path: str | Path | None = None) -> AppConfig:
    """Load config from JSON, merging over defaults and injecting env secrets."""
    if path is None:
        path = os.environ.get("SMART_CAM_CONFIG", str(ROOT / "config.json"))

    data: dict[str, Any] = {}
    p = Path(path)
    if p.exists():
        data = json.loads(p.read_text(encoding="utf-8"))

    cfg = AppConfig()
    if "sources" in data and isinstance(data["sources"], list):
        cfg.sources = [_source_from_dict(s) for s in data["sources"]]
    if "zones" in data and isinstance(data["zones"], list):
        cfg.zones = [_zone_from_dict(z) for z in data["zones"]]

    for section, dc in (
        ("detection", cfg.detection),
        ("events", cfg.events),
        ("privacy", cfg.privacy),
        ("retention", cfg.retention),
        ("auth", cfg.auth),
        ("webhook", cfg.webhook),
        ("report", cfg.report),
        ("alpr", cfg.alpr),
        ("face", cfg.face),
        ("reid", cfg.reid),
        ("vlm", cfg.vlm),
        ("notify", cfg.notify),
        ("storage", cfg.storage),
    ):
        if section in data and isinstance(data[section], dict):
            for key, value in data[section].items():
                if hasattr(dc, key):
                    setattr(dc, key, value)

    if "auth" in data and isinstance(data["auth"], dict) and isinstance(data["auth"].get("users"), list):
        cfg.auth.users = [
            AuthUser(username=u.get("username", ""), password_hash=u.get("password_hash", ""), role=u.get("role", "viewer"))
            for u in data["auth"]["users"]
        ]

    cfg = _apply_env_secrets(cfg)
    for err in validate_config(cfg):
        log.warning("config validation: %s", err)
    return cfg


def _simple_vars(dc: Any) -> dict[str, Any]:
    return vars(dc).copy()


def config_to_dict(cfg: AppConfig) -> dict[str, Any]:
    return {
        "sources": [_source_to_dict(s) for s in cfg.sources],
        "zones": [_zone_to_dict(z) for z in cfg.zones],
        "detection": _simple_vars(cfg.detection),
        "events": _simple_vars(cfg.events),
        "privacy": _simple_vars(cfg.privacy),
        "retention": _simple_vars(cfg.retention),
        "auth": {"enabled": cfg.auth.enabled, "users": [vars(u) for u in cfg.auth.users]},
        "webhook": _simple_vars(cfg.webhook),
        "report": _simple_vars(cfg.report),
        "alpr": _simple_vars(cfg.alpr),
        "face": _simple_vars(cfg.face),
        "reid": _simple_vars(cfg.reid),
        "vlm": _simple_vars(cfg.vlm),
        "notify": _simple_vars(cfg.notify),
        "storage": _simple_vars(cfg.storage),
        "webrtc": _simple_vars(cfg.webrtc),
        "workers": cfg.workers,
    }


def validate_config(cfg: AppConfig) -> list[str]:
    """Return a list of human-readable config errors (empty = valid)."""
    errors: list[str] = []
    seen: set[str] = set()
    for s in cfg.sources:
        if not s.id:
            errors.append("source has an empty id")
        elif s.id in seen:
            errors.append("duplicate source id: " + s.id)
        seen.add(s.id)
        if not s.uri:
            errors.append("source " + s.id + " has an empty uri")
    d = cfg.detection
    if not d.model:
        errors.append("detection.model is empty")
    if d.imgsz < 160:
        errors.append("detection.imgsz must be >= 160")
    if not (0.01 <= d.conf <= 1.0):
        errors.append("detection.conf must be 0.01-1.0")
    if not (0.01 <= d.iou <= 1.0):
        errors.append("detection.iou must be 0.01-1.0")
    if d.frame_stride < 1:
        errors.append("detection.frame_stride must be >= 1")
    if d.device not in ("cpu", "cuda", "mps", "auto"):
        errors.append("detection.device must be cpu, cuda, mps or auto")
    for z in cfg.zones:
        if len(z.points) < 3:
            errors.append("zone " + z.id + " has fewer than 3 points")
        else:
            for p in z.points:
                if len(p) != 2 or not (0.0 <= p[0] <= 1.0 and 0.0 <= p[1] <= 1.0):
                    errors.append("zone " + z.id + " has a point outside 0..1")
                    break
    if cfg.retention.retention_days < 0:
        errors.append("retention.retention_days must be >= 0")
    if not (0.0 <= cfg.face.min_conf <= 1.0):
        errors.append("face.min_conf must be 0-1")
    if not (0.0 <= cfg.reid.min_conf <= 1.0):
        errors.append("reid.min_conf must be 0-1")
    if not (0.0 <= cfg.alpr.min_conf <= 1.0):
        errors.append("alpr.min_conf must be 0-1")
    if cfg.storage.provider not in ("local", "s3"):
        errors.append("storage.provider must be 'local' or 's3'")
    if cfg.workers < 1:
        errors.append("workers must be >= 1")
    return errors


def config_from_dict(data: dict[str, Any]) -> AppConfig:
    """Build an AppConfig from a dict, merging over defaults (no file I/O)."""
    cfg = AppConfig()
    if isinstance(data.get("sources"), list):
        cfg.sources = [_source_from_dict(s) for s in data["sources"]]
    if isinstance(data.get("zones"), list):
        cfg.zones = [_zone_from_dict(z) for z in data["zones"]]
    for section, dc in (
        ("detection", cfg.detection), ("events", cfg.events), ("privacy", cfg.privacy),
        ("retention", cfg.retention), ("auth", cfg.auth), ("webhook", cfg.webhook),
        ("report", cfg.report), ("alpr", cfg.alpr), ("face", cfg.face), ("reid", cfg.reid),
        ("vlm", cfg.vlm), ("notify", cfg.notify), ("storage", cfg.storage), ("webrtc", cfg.webrtc),
    ):
        if isinstance(data.get(section), dict):
            for key, value in data[section].items():
                if hasattr(dc, key):
                    setattr(dc, key, value)
    if isinstance(data.get("auth"), dict) and isinstance(data["auth"].get("users"), list):
        cfg.auth.users = [
            AuthUser(username=u.get("username", ""), password_hash=u.get("password_hash", ""), role=u.get("role", "viewer"))
            for u in data["auth"]["users"]
        ]
    if "workers" in data:
        try:
            cfg.workers = int(data["workers"])
        except (TypeError, ValueError):
            pass
    return _apply_env_secrets(cfg)


def save_config(cfg: AppConfig, path: str | Path | None = None) -> Path:
    """Persist the current config to JSON."""
    if path is None:
        path = ROOT / "config.json"
    data = {
        "sources": [_source_to_dict(s) for s in cfg.sources],
        "zones": [_zone_to_dict(z) for z in cfg.zones],
        "detection": _simple_vars(cfg.detection),
        "events": _simple_vars(cfg.events),
        "privacy": _simple_vars(cfg.privacy),
        "retention": _simple_vars(cfg.retention),
        "auth": {"enabled": cfg.auth.enabled, "users": [vars(u) for u in cfg.auth.users]},
        "webhook": _simple_vars(cfg.webhook),
        "report": _simple_vars(cfg.report),
        "alpr": _simple_vars(cfg.alpr),
        "face": _simple_vars(cfg.face),
        "reid": _simple_vars(cfg.reid),
        "vlm": _simple_vars(cfg.vlm),
        "notify": _simple_vars(cfg.notify),
        "storage": _simple_vars(cfg.storage),
        "webrtc": _simple_vars(cfg.webrtc),
        "workers": cfg.workers,
    }
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return p


def write_example_config(path: str | Path) -> Path:
    """Write a fully-commented example config for first-time users."""
    p = Path(path)
    example = {
        "_comment": "Copy this file to config.json and edit. Secrets can stay in env vars instead.",
        "workers": 2,
        "sources": [
            {
                "id": "camera-1",
                "name": "Front door",
                "uri": "0",
                "enabled": True,
                "loop": True,
                "_uri_hint": "Use '0' for webcam, 'rtsp://user:pass@host/stream', 'http://...', or a local video path.",
            }
        ],
        "zones": [
            {
                "id": "lobby",
                "name": "Lobby",
                "source_id": "",
                "points": [[0.1, 0.2], [0.9, 0.2], [0.9, 0.9], [0.1, 0.9]],
                "classes": ["person"],
                "max_occupancy": 8,
                "loiter_sec": 60.0,
                "restricted": False,
                "allowed_window": "",
                "parking": False,
                "capacity": None,
            }
        ],
        "detection": {
            "model": "yolov8n.onnx",
            "device": "cpu",
            "imgsz": 640,
            "conf": 0.35,
            "iou": 0.45,
            "tracker": "bytetrack.yaml",
            "frame_stride": 2,
            "classes": [],
            "motion_enabled": True,
            "motion_threshold": 0.005,
        },
        "events": {
            "trigger_classes": ["person", "car", "truck", "bus", "motorcycle", "bicycle"],
            "min_presence_sec": 1.0,
            "cooldown_sec": 15.0,
            "clip_pre_sec": 2.0,
            "clip_post_sec": 4.0,
            "clip_fps": 15.0,
            "clip_max_width": 1280,
            "fall_bbox_ratio": 1.15,
            "fall_min_sec": 2.0,
            "fall_pose_model": "yolov8n-pose.pt",
            "fall_angle_deg": 55.0,
            "abandoned_sec": 30.0,
            "abandoned_owner_radius_px": 220.0,
            "abandoned_classes": ["suitcase", "handbag", "backpack", "umbrella"],
        },
        "privacy": {"blur_enabled": True, "blur_mode": "face"},
        "retention": {"retention_days": 30, "purge_interval_sec": 3600},
        "auth": {
            "enabled": False,
            "users": [{"username": "admin", "password_hash": hash_password("changeme"), "role": "admin"}],
        },
        "webhook": {"enabled": False, "url": "", "timeout_sec": 10.0},
        "report": {"enabled": False, "interval": "daily", "notify": False},
        "alpr": {
            "enabled": False,
            "zones_only": True,
            "min_conf": 0.4,
            "throttle_sec": 5.0,
            "save_crop": True,
            "languages": "en",
            "plate_model": "",
        },
        "face": {
            "enabled": False,
            "model_name": "Facenet",
            "detector_backend": "yolov8",
            "min_conf": 0.4,
            "throttle_sec": 5.0,
            "save_crop": True,
        },
        "reid": {
            "enabled": False,
            "model_name": "osnet_x0_25",
            "min_conf": 0.55,
            "throttle_sec": 3.0,
            "save_crop": True,
        },
        "vlm": {
            "enabled": True,
            "provider": "openai",
            "base_url": "https://api.openai.com/v1",
            "api_key": "",
            "model": "gpt-4o-mini",
            "max_keyframes": 3,
            "timeout_sec": 60,
        },
        "notify": {
            "enabled": True,
            "apprise_url": "ntfy://your-topic",
            "e2e_encrypt": False,
            "ntfy_topic": "",
            "ntfy_public_key": "",
            "ntfy_server": "https://ntfy.sh",
        },
        "webrtc": {
            "enabled": True,
            "stun_urls": ["stun:stun.l.google.com:19302"],
            "turn_url": "",
            "turn_username": "",
            "turn_credential": "",
        },
    }
    p.write_text(json.dumps(example, indent=2), encoding="utf-8")
    return p
