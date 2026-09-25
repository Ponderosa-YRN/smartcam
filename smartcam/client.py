"""HTTP client for the SmartCam API (remote mode)."""
from __future__ import annotations

import types

import numpy as np

from .config import AppConfig, config_from_dict


class _Store:
    def __init__(self, client):
        self.client = client

    def list_events(self, limit=100, camera_id=None, event_type=None, since=None, until=None, order="DESC"):
        params = {"limit": limit, "order": order}
        if camera_id:
            params["camera_id"] = camera_id
        if event_type:
            params["event_type"] = event_type
        if since is not None:
            params["since"] = since
        if until is not None:
            params["until"] = until
        r = self.client._get("/api/events", params)
        return r.json() if r.status_code == 200 else []

    def count_events(self):
        r = self.client._get("/api/count")
        return r.json().get("events", 0) if r.status_code == 200 else 0

    def list_plates(self, limit=100):
        r = self.client._get("/api/plates", {"limit": limit})
        return r.json() if r.status_code == 200 else []

    def search_plates(self, term, limit=100):
        t = term.strip().upper()
        return [p for p in self.list_plates(limit=1000) if t in (p.get("plate") or "").upper()][:limit]

    def list_faces(self):
        r = self.client._get("/api/faces")
        return r.json() if r.status_code == 200 else []

    def delete_face(self, face_id):
        self.client._delete("/api/faces/" + str(face_id))

    def add_face(self, name, role, embedding, thumb_path=None, consent=0):
        r = self.client._post("/api/faces", {"name": name, "role": role, "embedding": list(embedding), "thumb_path": thumb_path, "consent": 1 if consent else 0})
        return r.json().get("id") if r.status_code == 200 else None

    def delete_person(self, name=None, face_id=None):
        self.client._post("/api/delete_person", {"name": name, "face_id": face_id})

    def list_face_matches(self, limit=100):
        r = self.client._get("/api/face_matches", {"limit": limit})
        return r.json() if r.status_code == 200 else []

    def list_identities(self):
        r = self.client._get("/api/identities")
        return r.json() if r.status_code == 200 else []

    def delete_identity(self, identity_id):
        self.client._delete("/api/identities/" + str(identity_id))

    def add_identity(self, name, face_id, embedding, thumb_path=None):
        r = self.client._post("/api/identities", {"name": name, "face_id": face_id, "embedding": list(embedding), "thumb_path": thumb_path})
        return r.json().get("id") if r.status_code == 200 else None

    def list_sightings(self, identity_id):
        r = self.client._get("/api/sightings/" + str(identity_id))
        return r.json() if r.status_code == 200 else []

    def list_occupancy_samples(self, since=None, limit=2000):
        params = {"limit": limit}
        if since is not None:
            params["since"] = since
        r = self.client._get("/api/occupancy_history", params)
        return r.json() if r.status_code == 200 else []

    def acknowledge(self, event_id):
        self.client._post("/api/ack/" + str(event_id))

    def resolve(self, event_id):
        self.client._post("/api/resolve/" + str(event_id))

    def assign(self, event_id, user):
        self.client._post("/api/assign/" + str(event_id), {"user": user})

    def escalate(self, event_id):
        self.client._post("/api/escalate/" + str(event_id))

    def list_open_alerts(self, limit=200):
        r = self.client._get("/api/open_alerts", {"limit": limit})
        return r.json() if r.status_code == 200 else []


class _RemotePipeline:
    def __init__(self, client, source_id):
        self.client = client
        self.source_id = source_id
        self.source = None

    @property
    def stats(self):
        r = self.client._get("/api/status/" + self.source_id)
        if r.status_code == 200:
            return r.json()
        return {"status": "unknown", "fps": 0.0, "frames": 0, "active_objects": [], "zones": [], "error": ""}

    @property
    def latest_frame(self):
        import cv2

        r = self.client._get("/api/frame/" + self.source_id)
        if r.status_code == 200 and r.content:
            buf = np.frombuffer(r.content, np.uint8)
            return cv2.imdecode(buf, cv2.IMREAD_COLOR)
        return None

    @property
    def running(self):
        return self.stats.get("status") == "running"

    def health(self):
        import time as _time

        s = self.stats
        if s.get("status") == "error":
            return "offline"
        if s.get("status") == "running":
            lt = s.get("last_frame_ts")
            if lt is not None and _time.time() - lt > 30:
                return "stalled"
            return "healthy"
        return "stopped"

    def start(self):
        self.client._post("/api/start/" + self.source_id)

    def stop(self):
        self.client._post("/api/stop/" + self.source_id)

    @property
    def heatmap(self):
        return _RemoteHeatmap(self.client, self.source_id)


class _RemoteHeatmap:
    def __init__(self, client, source_id):
        self.client = client
        self.source_id = source_id

    def render(self, path):
        from pathlib import Path

        r = self.client._get("/api/heatmap/" + self.source_id)
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if r.status_code == 200 and r.content:
            p.write_bytes(r.content)
        return p


class _FaceEngineRemote:
    def __init__(self, client):
        self.client = client

    def detect_and_embed(self, img):
        import cv2

        ok, buf = cv2.imencode(".jpg", img[:, :, ::-1])  # RGB -> BGR for JPEG
        if not ok:
            return []
        r = self.client._post_files("/api/embed_face", {"image": ("face.jpg", buf.tobytes(), "image/jpeg")})
        if r.status_code == 200:
            return [{"embedding": np.asarray(f["embedding"], dtype=np.float32), "box": f["box"]} for f in r.json()]
        return []


class _ReidEngineRemote:
    def __init__(self, client):
        self.client = client

    def embed(self, img):
        import cv2

        ok, buf = cv2.imencode(".jpg", img[:, :, ::-1])  # RGB -> BGR for JPEG
        if not ok:
            return None
        r = self.client._post_files("/api/embed_reid", {"image": ("img.jpg", buf.tobytes(), "image/jpeg")})
        if r.status_code == 200:
            e = r.json().get("embedding")
            return np.asarray(e, dtype=np.float32) if e else None
        return None


class ApiClient:
    """Mirrors PipelineManager's interface over HTTP."""

    def __init__(self, base_url):
        import requests

        self.base_url = base_url.rstrip("/")
        self._s = requests.Session()
        self._token = None
        self._device_token = None
        self.store = _Store(self)
        self.face_engine = _FaceEngineRemote(self)
        self.reid_engine = _ReidEngineRemote(self)
        self.detector = types.SimpleNamespace(names={})
        self.pipelines = {}
        self._cfg = AppConfig()
        self._reload()

    def _reload(self):
        try:
            self._cfg = config_from_dict(self._s.get(self.base_url + "/api/config", timeout=8, headers=self._headers()).json())
        except Exception:
            self._cfg = AppConfig()
        try:
            self.detector.names = self._s.get(self.base_url + "/api/class_names", timeout=8, headers=self._headers()).json() or {}
        except Exception:
            self.detector.names = {}
        self.pipelines = {}
        for s in self._cfg.sources:
            p = _RemotePipeline(self, s.id)
            p.source = s
            self.pipelines[s.id] = p

    @property
    def cfg(self):
        return self._cfg

    def _headers(self):
        if self._device_token:
            return {"Authorization": "Device " + self._device_token}
        return {"Authorization": "Bearer " + self._token} if self._token else {}

    def set_token(self, token):
        self._token = token

    def set_device_token(self, token):
        self._device_token = token

    def login(self, username, password):
        """Authenticate and store the access token. Returns the role, or None."""
        r = self._s.post(self.base_url + "/auth/login", json={"username": username, "password": password}, timeout=15)
        if r.status_code != 200:
            return None
        data = r.json()
        self._token = data.get("access_token")
        self._reload()
        return data.get("role")

    def _get(self, path, params=None):
        return self._s.get(self.base_url + path, params=params, timeout=10, headers=self._headers())

    def _post(self, path, json_data=None):
        return self._s.post(self.base_url + path, json=json_data, timeout=20, headers=self._headers())

    def _post_files(self, path, files):
        return self._s.post(self.base_url + path, files=files, timeout=120, headers=self._headers())

    def _delete(self, path):
        return self._s.delete(self.base_url + path, timeout=10, headers=self._headers())

    def search(self, query, camera_id=None, limit=50):
        params = {"q": query, "limit": limit}
        if camera_id:
            params["camera_id"] = camera_id
        r = self._get("/api/search", params)
        return r.json() if r.status_code == 200 else []

    def add_source(self, source):
        self._post("/api/sources", {"id": source.id, "name": source.name, "uri": source.uri, "enabled": source.enabled, "loop": source.loop})
        self._reload()
        return source.id

    def remove_source(self, source_id):
        self._delete("/api/sources/" + str(source_id))
        self._reload()

    def save_config(self, cfg):
        from .config import config_to_dict

        self._post("/api/config", config_to_dict(cfg))

    def occupancy(self):
        r = self._get("/api/occupancy")
        return r.json() if r.status_code == 200 else {"people": 0, "vehicles": 0, "cameras": {}}

    # -- edge ingestion (device token) -----------------------------------
    def ingest_events(self, events):
        r = self._post("/api/ingest/events", {"events": events})
        return r.json() if r.status_code == 200 else None

    def ingest_occupancy(self, samples):
        r = self._post("/api/ingest/occupancy", {"samples": samples})
        return r.json() if r.status_code == 200 else None

    def ingest_media(self, event_id, clip_path=None, thumb_path=None):
        import os

        files = {}
        if clip_path and os.path.exists(clip_path):
            files["clip"] = (os.path.basename(clip_path), open(clip_path, "rb"), "video/mp4")
        if thumb_path and os.path.exists(thumb_path):
            files["thumb"] = (os.path.basename(thumb_path), open(thumb_path, "rb"), "image/jpeg")
        if not files:
            return None
        try:
            return self._post_files("/api/ingest/media/" + str(event_id), files)
        finally:
            for _name, fh, _ct in files.values():
                fh.close()

    def heartbeat(self):
        return self._post("/device/heartbeat")
