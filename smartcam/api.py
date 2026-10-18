"""FastAPI backend: runs the pipeline headlessly and serves a REST API.

Run with:
    .venv\\Scripts\\python run_api.py
"""
from __future__ import annotations

import hmac
import logging
import os
import re
import time
from pathlib import Path
from contextlib import asynccontextmanager

import asyncio

from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse

from .audit import audit_log
from .auth import ROLES, authenticate_user, bootstrap_admin
from .config import config_from_dict, config_to_dict, load_config
from .pipeline import PipelineManager
from .search import SmartSearch
from .security import create_token, hash_password, load_or_create_secret, read_token
from .secrets import issue_device_token, parse_device_token
from .storage import get_storage
from .billing import PLANS, plan_limits, tenant_usage
from .utils import frame_to_jpeg_bytes

log = logging.getLogger("smartcam.api")

_manager: PipelineManager | None = None


def _cloud_only() -> bool:
    return os.environ.get("SMART_CAM_CLOUD_ONLY", "").strip().lower() in ("1", "true", "yes", "on")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _manager
    cfg = load_config()
    if _cloud_only():
        from .control import ControlPlaneManager

        _manager = ControlPlaneManager(cfg)
        log.info("SmartCam API started in cloud-only (control-plane) mode")
    else:
        _manager = PipelineManager(cfg)
        log.info("SmartCam API started with %d source(s)", len(cfg.sources))
    if not bootstrap_admin(_manager.store) and _manager.store.count_users() == 0:
        log.warning("No users exist: run scripts/create_user.py or set SMART_CAM_ADMIN_PASSWORD")
    yield
    if _manager is not None:
        _manager.stop_all()


app = FastAPI(title="SmartCam API", version="0.1.0", lifespan=lifespan)

_cors_origins = [o.strip() for o in os.environ.get("SMART_CAM_CORS_ORIGINS", "*").split(",") if o.strip()]
# NOTE: CORSMiddleware is registered further down, *after* auth_middleware, on purpose.
# Starlette applies the most recently added middleware outermost, so adding CORS last
# keeps it wrapped around auth_middleware. Registered here it would sit inside it, and
# the 401 auth_middleware returns would reach the browser with no CORS headers at all -
# which surfaces as an opaque "Failed to fetch" instead of a readable error.


def _mgr() -> PipelineManager:
    if _manager is None:
        raise HTTPException(status_code=503, detail="pipeline not initialized")
    return _manager


ACCESS_TOKEN_MAX_AGE = 12 * 3600
REFRESH_TOKEN_MAX_AGE = 30 * 24 * 3600

_PUBLIC_PATHS = {
    "/api/health", "/auth/login", "/auth/refresh", "/auth/register",
    "/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc",
}

# Login throttling. In-memory and per-process, which is enough for one API container.
# ponytail: in-memory throttle, move it into the event store if the API is scaled out.
_LOGIN_FAILS: dict[str, list[float]] = {}
_LOGIN_MAX_FAILS = 8
_LOGIN_WINDOW_SEC = 300.0


def _login_key(request: Request, username: str) -> str:
    host = request.client.host if request.client else "?"
    return host + "|" + username.lower()


def _login_blocked(key: str) -> bool:
    now = time.time()
    hits = [t for t in _LOGIN_FAILS.get(key, []) if now - t < _LOGIN_WINDOW_SEC]
    _LOGIN_FAILS[key] = hits
    return len(hits) >= _LOGIN_MAX_FAILS


# Signup is the only unauthenticated write path, so cap how fast one host can use it.
_SIGNUPS: dict[str, list[float]] = {}
_SIGNUP_MAX = 5
_SIGNUP_WINDOW_SEC = 3600.0

# Ceiling for a single uploaded file, shared by the dashboard upload and device ingest.
_UPLOAD_MAX_BYTES = 2 * 1024 ** 3
_UPLOAD_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v"}


def _audit(role: str, action: str, detail: str = "") -> None:
    """Append to the audit trail. Best-effort, never blocks the request."""
    try:
        audit_log(_mgr().cfg.data_dir / "audit.log", role, action, detail)
    except Exception:
        pass


def _signup_enabled() -> bool:
    """Public sign-up is closed unless SMART_CAM_ALLOW_SIGNUP is set.

    Self-serve registration creates a tenant and its first admin from an unauthenticated
    request, so it is the whole attack surface of the product in one call. Closed by
    default means an open deployment is an explicit choice, not an accident.
    """
    return os.environ.get("SMART_CAM_ALLOW_SIGNUP", "").strip().lower() in ("1", "true", "yes", "on")


def _signup_allowed(request: Request) -> bool:
    host = request.client.host if request.client else "?"
    now = time.time()
    hits = [t for t in _SIGNUPS.get(host, []) if now - t < _SIGNUP_WINDOW_SEC]
    if len(hits) >= _SIGNUP_MAX:
        _SIGNUPS[host] = hits
        return False
    hits.append(now)
    _SIGNUPS[host] = hits
    return True


def _require_platform_key(request: Request) -> None:
    """Plan and billing status are money, so only the operator may set them.

    Both used to be writable by any tenant admin through their own billing route, which
    let a customer move themselves onto the top plan for free. No env var means closed.
    """
    expected = os.environ.get("SMART_CAM_PLATFORM_KEY", "")
    if not expected or not hmac.compare_digest(request.headers.get("x-platform-key", ""), expected):
        raise HTTPException(status_code=403, detail="plan changes require a platform key")


_token_secret = ""


def _get_secret() -> str:
    global _token_secret
    if not _token_secret:
        _token_secret = load_or_create_secret(load_config().data_dir / ".token_secret")
    return _token_secret


def _require_role(request: Request, *roles: str) -> None:
    user = getattr(request.state, "user", None)
    if user is None or user.get("role") not in roles:
        raise HTTPException(status_code=403, detail="Insufficient permissions")


def _req_tenant(request: Request) -> int | None:
    return getattr(request.state, "user", {}).get("tenant_id")


def _require_own_tenant(request: Request, tenant_id: int) -> None:
    """Require a tenant admin acting on their own tenant.

    The tenant id comes from the path, so without the comparison one customer's admin
    could list, create or delete another customer's sites, devices and invites - and
    create_device hands back a device token for that other tenant.
    """
    _require_role(request, "admin")
    if tenant_id != _req_tenant(request):
        raise HTTPException(status_code=404, detail="tenant not found")


def _require_user_in_tenant(request: Request, user_id: int) -> None:
    u = _mgr().store.get_user(user_id)
    if u is None or u.get("tenant_id") != _req_tenant(request):
        raise HTTPException(status_code=404, detail="user not found")


def _event_for_tenant(request: Request, event_id: int) -> dict | None:
    """Fetch an event only if it belongs to the caller's tenant.

    The media endpoints used to accept any event id, so one hotel could read another
    hotel's clips and thumbnails by counting upwards from 1.
    """
    ev = _mgr().store.get_event(event_id)
    if ev is None or ev.get("tenant_id") != _req_tenant(request):
        return None
    return ev


def _tenant_can_see_source(tenant: int | None, source_id: str) -> bool:
    """True when this tenant may watch or control this camera.

    A camera with no tenant_id is shared (a demo feed); otherwise it belongs to exactly
    one tenant.
    """
    for s in _mgr().cfg.sources:
        if s.id == source_id:
            return s.tenant_id is None or s.tenant_id == tenant
    return False


def _can_see_source(request: Request, source_id: str) -> bool:
    return _tenant_can_see_source(_req_tenant(request), source_id)


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "tenant"


def _resolve_device(request: Request) -> dict | None:
    """Resolve a device identity from a device token (Authorization: Device ... or X-Device-Token)."""
    header = request.headers.get("authorization", "")
    token = header[7:].strip() if header.lower().startswith("device ") else ""
    if not token:
        token = request.headers.get("x-device-token", "").strip()
    if not token:
        return None
    claims = parse_device_token(_get_secret(), token)
    if claims is None:
        return None
    dev = _mgr().store.get_device(claims["device_id"])
    if dev is None or dev.get("tenant_id") != claims["tenant_id"]:
        return None
    if int(dev.get("token_generation", 0)) != claims["gen"]:
        return None
    return {"role": "device", "tenant_id": claims["tenant_id"], "device_id": claims["device_id"], "typ": "device"}


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if path in _PUBLIC_PATHS or path.startswith("/invites/") or request.method == "OPTIONS":
        return await call_next(request)
    header = request.headers.get("authorization", "")
    token = header[7:].strip() if header.lower().startswith("bearer ") else ""
    payload = read_token(token, _get_secret(), ACCESS_TOKEN_MAX_AGE) if token else None
    if payload is not None and payload.get("typ") == "access":
        if _manager is None:
            return JSONResponse({"detail": "starting"}, status_code=503)
        # The token is good for 12 hours, so a deleted or demoted account would otherwise
        # keep its old role for that whole window. Re-read the row and trust it instead.
        # ponytail: one user lookup per request; cache it if request volume ever matters.
        user = _manager.store.get_user(int(payload.get("sub", 0)))
        if user is None:
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)
        payload = {**payload, "role": user["role"], "tenant_id": user.get("tenant_id")}
        request.state.user = payload
        return await call_next(request)
    device = _resolve_device(request)
    if device is not None:
        request.state.user = device
        request.state.device = device
        return await call_next(request)
    return JSONResponse({"detail": "Not authenticated"}, status_code=401)


# Outermost middleware (see the note above where the origins are parsed): registered
# after auth_middleware so every response - including auth 401s - carries CORS headers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/auth/register")
def register(request: Request, data: dict):
    if not _signup_enabled():
        raise HTTPException(
            status_code=403,
            detail="Sign-up is closed. Ask an administrator for an invitation.",
        )
    if not _signup_allowed(request):
        raise HTTPException(status_code=429, detail="Too many signups from this address. Try again later.")
    company = str(data.get("company", "")).strip()
    slug = str(data.get("slug", "")).strip().lower() or _slugify(company)
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    if not company or not username or not password:
        raise HTTPException(status_code=400, detail="company, username and password are required")
    if _mgr().store.get_tenant_by_slug(slug) is not None:
        raise HTTPException(status_code=409, detail="company name already taken")
    if _mgr().store.get_user_by_username(username) is not None:
        raise HTTPException(status_code=409, detail="username already exists")
    tid = _mgr().store.create_tenant(slug, company)
    uid = _mgr().store.create_user(username, hash_password(password), role="admin", tenant_id=tid)
    _audit("admin", "tenant.register", f"slug={slug} user={username}")
    secret = _get_secret()
    access = create_token({"sub": uid, "username": username, "role": "admin", "tenant_id": tid, "typ": "access"}, secret)
    refresh = create_token({"sub": uid, "typ": "refresh"}, secret)
    return {
        "access_token": access, "refresh_token": refresh, "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_MAX_AGE, "role": "admin", "username": username, "tenant_id": tid,
    }


@app.post("/auth/login")
def login(request: Request, data: dict):
    username = str(data.get("username", ""))
    password = str(data.get("password", ""))
    key = _login_key(request, username)
    if _login_blocked(key):
        raise HTTPException(
            status_code=429,
            detail="Too many failed sign-in attempts. Wait a few minutes and try again.",
        )
    user = authenticate_user(_mgr().store, username, password)
    if user is None:
        _LOGIN_FAILS.setdefault(key, []).append(time.time())
        _audit("-", "login.fail", f"user={username} key={key}")
        raise HTTPException(status_code=401, detail="Invalid username or password")
    _LOGIN_FAILS.pop(key, None)
    _audit(user["role"], "login.ok", f"user={user['username']}")
    secret = _get_secret()
    access = create_token({"sub": user["id"], "username": user["username"], "role": user["role"], "tenant_id": user.get("tenant_id"), "typ": "access"}, secret)
    refresh = create_token({"sub": user["id"], "typ": "refresh"}, secret)
    return {
        "access_token": access, "refresh_token": refresh, "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_MAX_AGE, "role": user["role"], "username": user["username"],
    }


@app.post("/auth/refresh")
def refresh(data: dict):
    payload = read_token(str(data.get("refresh_token", "")), _get_secret(), REFRESH_TOKEN_MAX_AGE)
    if payload is None or payload.get("typ") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user = _mgr().store.get_user(int(payload.get("sub", 0)))
    if user is None:
        raise HTTPException(status_code=401, detail="Unknown user")
    secret = _get_secret()
    return {
        "access_token": create_token({"sub": user["id"], "username": user["username"], "role": user["role"], "tenant_id": user.get("tenant_id"), "typ": "access"}, secret),
        "refresh_token": create_token({"sub": user["id"], "typ": "refresh"}, secret),
        "token_type": "bearer", "expires_in": ACCESS_TOKEN_MAX_AGE,
    }


@app.post("/auth/logout")
def logout(request: Request):
    # Stateless tokens: no server-side revocation in P0; the client discards them.
    return {"ok": True}


@app.get("/auth/me")
def me(request: Request):
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"id": user.get("sub"), "username": user.get("username"), "role": user.get("role"), "tenant_id": user.get("tenant_id")}


@app.get("/auth/users")
def list_users(request: Request):
    _require_role(request, "admin")
    return [
        {"id": u["id"], "username": u["username"], "role": u["role"], "tenant_id": u.get("tenant_id"), "created_at": u.get("created_at")}
        for u in _mgr().store.list_users(_req_tenant(request))
    ]


@app.post("/auth/users")
def create_user(request: Request, data: dict):
    _require_role(request, "admin")
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    role = data.get("role", "viewer")
    if not username or not password:
        raise HTTPException(status_code=400, detail="username and password are required")
    if role not in ROLES:
        raise HTTPException(status_code=400, detail="invalid role")
    if _mgr().store.get_user_by_username(username) is not None:
        raise HTTPException(status_code=409, detail="username already exists")
    # Never trust a supplied tenant_id: an admin may only add users to their own tenant.
    tenant_id = _req_tenant(request)
    uid = _mgr().store.create_user(username, hash_password(password), role=role, tenant_id=tenant_id)
    _audit("admin", "user.create", f"user={username} role={role} tenant={tenant_id}")
    return {"id": uid, "username": username, "role": role, "tenant_id": tenant_id}


@app.put("/auth/users/{user_id}")
def update_user(request: Request, user_id: int, data: dict):
    _require_role(request, "admin")
    _require_user_in_tenant(request, user_id)
    fields: dict = {}
    if data.get("role") in ROLES:
        fields["role"] = data["role"]
    if data.get("password"):
        fields["password_hash"] = hash_password(str(data["password"]))
    if not fields:
        raise HTTPException(status_code=400, detail="nothing to update")
    _mgr().store.update_user(user_id, **fields)
    _audit("admin", "user.update", f"id={user_id} fields={','.join(sorted(fields))}")
    return {"ok": True}


@app.delete("/auth/users/{user_id}")
def delete_user(request: Request, user_id: int):
    _require_role(request, "admin")
    _require_user_in_tenant(request, user_id)
    _mgr().store.delete_user(user_id)
    _audit("admin", "user.delete", f"id={user_id}")
    return {"ok": True}


@app.get("/tenants")
def list_tenants(request: Request):
    _require_role(request, "admin")
    return [t for t in _mgr().store.list_tenants() if t["id"] == _req_tenant(request)]


@app.post("/tenants")
def create_tenant(request: Request, data: dict):
    _require_role(request, "admin")
    slug = str(data.get("slug", "")).strip()
    name = str(data.get("name", "")).strip() or slug
    if not slug:
        raise HTTPException(status_code=400, detail="slug is required")
    if _mgr().store.get_tenant_by_slug(slug) is not None:
        raise HTTPException(status_code=409, detail="tenant slug already exists")
    tid = _mgr().store.create_tenant(slug, name)
    return {"id": tid, "slug": slug, "name": name}


@app.delete("/tenants/{tenant_id}")
def delete_tenant(request: Request, tenant_id: int):
    _require_own_tenant(request, tenant_id)
    _mgr().store.delete_tenant(tenant_id)
    return {"ok": True}


@app.get("/tenants/{tenant_id}/sites")
def tenant_sites(request: Request, tenant_id: int):
    _require_own_tenant(request, tenant_id)
    return _mgr().store.list_sites(tenant_id)


@app.post("/tenants/{tenant_id}/sites")
def create_site(request: Request, tenant_id: int, data: dict):
    _require_own_tenant(request, tenant_id)
    name = str(data.get("name", "")).strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    sid = _mgr().store.create_site(tenant_id, name, str(data.get("timezone", "")))
    return {"id": sid, "name": name}


@app.get("/tenants/{tenant_id}/devices")
def tenant_devices(request: Request, tenant_id: int):
    _require_own_tenant(request, tenant_id)
    return _mgr().store.list_devices(tenant_id)


@app.post("/tenants/{tenant_id}/devices")
def create_device(request: Request, tenant_id: int, data: dict):
    _require_own_tenant(request, tenant_id)
    name = str(data.get("name", "")).strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    site_id = data.get("site_id")
    did = _mgr().store.create_device(tenant_id, name, site_id=int(site_id) if site_id else None)
    token = issue_device_token(_get_secret(), tenant_id, did, 0)
    return {"id": did, "name": name, "tenant_id": tenant_id, "token": token}


@app.post("/tenants/{tenant_id}/devices/{device_id}/rotate-token")
def rotate_device_token(request: Request, tenant_id: int, device_id: int):
    _require_own_tenant(request, tenant_id)
    dev = _mgr().store.get_device(device_id)
    if dev is None or dev.get("tenant_id") != tenant_id:
        raise HTTPException(status_code=404, detail="device not found")
    gen = _mgr().store.bump_device_token_generation(device_id)
    token = issue_device_token(_get_secret(), tenant_id, device_id, gen)
    return {"device_id": device_id, "generation": gen, "token": token}


@app.delete("/tenants/{tenant_id}/devices/{device_id}")
def delete_device(request: Request, tenant_id: int, device_id: int):
    _require_own_tenant(request, tenant_id)
    dev = _mgr().store.get_device(device_id)
    if dev is None or dev.get("tenant_id") != tenant_id:
        raise HTTPException(status_code=404, detail="device not found")
    _mgr().store.delete_device(device_id)
    return {"ok": True}


@app.get("/device/me")
def device_me(request: Request):
    _require_role(request, "device")
    return {"tenant_id": request.state.user.get("tenant_id"), "device_id": request.state.user.get("device_id")}


@app.post("/device/heartbeat")
def device_heartbeat(request: Request):
    _require_role(request, "device")
    _mgr().store.touch_device(int(request.state.user.get("device_id", 0)))
    return {"ok": True}


def _normalize_event(ev: dict) -> dict:
    """Sanitize an edge-reported event into the fields add_event expects."""

    def _num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    objects = ev.get("objects") or []
    if isinstance(objects, str):
        objects = [objects]
    track_ids = ev.get("track_ids") or []
    if isinstance(track_ids, str):
        track_ids = [track_ids]
    return {
        "camera_id": str(ev.get("camera_id", "edge-camera")),
        "camera_name": str(ev.get("camera_name", "")),
        "start_ts": _num(ev.get("start_ts")),
        "end_ts": _num(ev.get("end_ts")),
        "duration": _num(ev.get("duration")),
        "objects": [str(o) for o in objects],
        "top_object": ev.get("top_object"),
        "track_ids": [str(t) for t in track_ids],
        "max_conf": _num(ev.get("max_conf")),
        "event_type": str(ev.get("event_type", "detection")),
        "summary": ev.get("summary"),
    }


@app.post("/api/ingest/events")
def ingest_events(request: Request, data: dict):
    """Device auth: batch-ingest detection events, stamped with tenant + device."""
    _require_role(request, "device")
    dev = request.state.user
    events = data.get("events")
    if not isinstance(events, list):
        raise HTTPException(status_code=400, detail="events must be a list")
    ids = []
    for ev in events[:500]:
        if not isinstance(ev, dict):
            continue
        ids.append(_mgr().store.add_event(_normalize_event(ev), tenant_id=dev["tenant_id"], device_id=dev["device_id"]))
    return {"created": ids}


@app.post("/api/ingest/occupancy")
def ingest_occupancy(request: Request, data: dict):
    """Device auth: batch-ingest occupancy samples, stamped with tenant + device."""
    _require_role(request, "device")
    dev = request.state.user
    samples = data.get("samples")
    if not isinstance(samples, list):
        raise HTTPException(status_code=400, detail="samples must be a list")
    n = 0
    for s in samples[:2000]:
        if not isinstance(s, dict):
            continue
        try:
            ts = float(s.get("ts", time.time()))
            people = int(s.get("people", 0))
            vehicles = int(s.get("vehicles", 0))
        except (TypeError, ValueError):
            continue
        _mgr().store.add_occupancy_sample(ts, people, vehicles, tenant_id=dev["tenant_id"], device_id=dev["device_id"])
        n += 1
    return {"created": n}


async def _write_capped(file: UploadFile, dest: Path) -> None:
    """Stream an upload to disk, discarding it once it passes _UPLOAD_MAX_BYTES.

    Both upload paths used to copy whatever they were sent straight to disk.
    """
    written = 0
    try:
        with open(dest, "wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > _UPLOAD_MAX_BYTES:
                    raise HTTPException(status_code=413, detail="upload too large")
                f.write(chunk)
    except HTTPException:
        dest.unlink(missing_ok=True)
        raise


async def _save_upload(base_dir: Path, event_id: int, file: UploadFile, kind: str) -> str:
    base_dir.mkdir(parents=True, exist_ok=True)
    # The extension came straight from the client, so anything outside this set could drop
    # an arbitrary file type into the media directory.
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _UPLOAD_EXTS:
        ext = ".jpg" if kind == "thumb" else ".mp4"
    dest = base_dir / ("event_%d_%s%s" % (event_id, kind, ext))
    await _write_capped(file, dest)
    return str(dest)


@app.post("/api/ingest/media/{event_id}")
async def ingest_media(request: Request, event_id: int, clip: UploadFile = File(None), thumb: UploadFile = File(None)):
    """Device auth: attach a clip and/or thumbnail to a cloud event."""
    _require_role(request, "device")
    dev = request.state.user
    ev = _mgr().store.get_event(event_id)
    if ev is None or ev.get("tenant_id") != dev["tenant_id"]:
        raise HTTPException(status_code=404, detail="event not found")
    fields = {}
    if clip is not None:
        fields["clip_path"] = await _save_upload(_mgr().cfg.clips_dir, event_id, clip, "clip")
    if thumb is not None:
        fields["thumb_path"] = await _save_upload(_mgr().cfg.thumbs_dir, event_id, thumb, "thumb")
    if fields:
        _mgr().store.update_event(event_id, **fields)
    return {"event_id": event_id, **fields}


@app.post("/tenants/{tenant_id}/invites")
def create_invite(request: Request, tenant_id: int, data: dict):
    _require_own_tenant(request, tenant_id)
    email = str(data.get("email", "")).strip()
    role = data.get("role", "viewer")
    if not email or role not in ROLES:
        raise HTTPException(status_code=400, detail="email and a valid role are required")
    import secrets
    token = secrets.token_urlsafe(32)
    expires_at = time.time() + 7 * 86400
    iid = _mgr().store.create_invite(tenant_id, email, role, token, expires_at)
    return {"id": iid, "tenant_id": tenant_id, "email": email, "role": role, "token": token, "expires_at": expires_at}


@app.get("/tenants/{tenant_id}/invites")
def list_invites(request: Request, tenant_id: int):
    _require_own_tenant(request, tenant_id)
    return _mgr().store.list_invites(tenant_id)


@app.delete("/tenants/{tenant_id}/invites/{invite_id}")
def revoke_invite(request: Request, tenant_id: int, invite_id: int):
    _require_own_tenant(request, tenant_id)
    _mgr().store.delete_invite(invite_id)
    return {"ok": True}


@app.get("/invites/{token}")
def invite_preview(token: str):
    inv = _mgr().store.get_invite_by_token(token)
    if inv is None or inv.get("consumed") or (inv.get("expires_at") and inv["expires_at"] < time.time()):
        raise HTTPException(status_code=404, detail="invalid or expired invite")
    tenant = _mgr().store.get_tenant(inv["tenant_id"])
    return {"email": inv["email"], "role": inv["role"], "tenant": tenant["name"] if tenant else ""}


@app.post("/invites/{token}/accept")
def accept_invite(token: str, data: dict):
    inv = _mgr().store.get_invite_by_token(token)
    if inv is None or inv.get("consumed") or (inv.get("expires_at") and inv["expires_at"] < time.time()):
        raise HTTPException(status_code=400, detail="invalid or expired invite")
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    if not username or not password:
        raise HTTPException(status_code=400, detail="username and password are required")
    if _mgr().store.get_user_by_username(username) is not None:
        raise HTTPException(status_code=409, detail="username already exists")
    uid = _mgr().store.create_user(username, hash_password(password), role=inv["role"], tenant_id=inv["tenant_id"])
    _mgr().store.consume_invite(inv["id"])
    return {"id": uid, "username": username, "tenant_id": inv["tenant_id"], "role": inv["role"]}


@app.get("/plans")
def list_plans(request: Request):
    _require_role(request, "admin")
    return PLANS


@app.get("/tenants/{tenant_id}/usage")
def get_tenant_usage(request: Request, tenant_id: int):
    _require_own_tenant(request, tenant_id)
    tenant = _mgr().store.get_tenant(tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="unknown tenant")
    plan = tenant.get("plan", "free")
    return {
        "tenant": tenant["name"],
        "plan": plan,
        "billing_status": tenant.get("billing_status", "active"),
        "limits": plan_limits(plan),
        "usage": tenant_usage(_mgr().cfg, _mgr().store, tenant_id),
    }


@app.post("/tenants/{tenant_id}/billing")
def update_billing(request: Request, tenant_id: int, data: dict):
    _require_own_tenant(request, tenant_id)
    if data.get("plan") in PLANS or "billing_status" in data:
        _require_platform_key(request)
    fields: dict = {}
    if data.get("plan") in PLANS:
        fields["plan"] = data["plan"]
    if "billing_status" in data:
        fields["billing_status"] = str(data["billing_status"])
    for k in ("stripe_customer_id", "stripe_subscription_id"):
        if k in data:
            fields[k] = str(data[k])
    if not fields:
        raise HTTPException(status_code=400, detail="nothing to update")
    _mgr().store.update_tenant(tenant_id, **fields)
    return {"ok": True}


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "smartcam"}


@app.get("/api/sources")
def sources(request: Request):
    m = _mgr()
    tenant = _req_tenant(request)
    out = []
    for s in m.cfg.sources:
        if s.tenant_id is not None and s.tenant_id != tenant:
            continue
        p = m.pipelines.get(s.id)
        out.append({
            "id": s.id, "name": s.name, "uri": s.uri, "enabled": s.enabled,
            "running": bool(p.running if p else False),
            "status": p.stats["status"] if p else "unknown",
            "health": p.health() if p else "unknown",
        })
    return out


@app.post("/api/start/{source_id}")
def start(request: Request, source_id: str):
    _require_role(request, "admin", "manager")
    m = _mgr()
    if not _can_see_source(request, source_id) or source_id not in m.pipelines:
        raise HTTPException(status_code=404, detail="unknown source")
    m.start(source_id)
    return {"ok": True}


@app.post("/api/stop/{source_id}")
def stop(request: Request, source_id: str):
    _require_role(request, "admin", "manager")
    m = _mgr()
    if not _can_see_source(request, source_id) or source_id not in m.pipelines:
        raise HTTPException(status_code=404, detail="unknown source")
    m.stop(source_id)
    return {"ok": True}


@app.get("/api/status/{source_id}")
def status(request: Request, source_id: str):
    m = _mgr()
    p = m.pipelines.get(source_id)
    if p is None or not _can_see_source(request, source_id):
        raise HTTPException(status_code=404, detail="unknown source")
    return p.stats


@app.get("/api/frame/{source_id}")
def frame(request: Request, source_id: str):
    m = _mgr()
    p = m.pipelines.get(source_id)
    if p is None or p.latest_frame is None or not _can_see_source(request, source_id):
        raise HTTPException(status_code=404, detail="no frame available")
    jpg = frame_to_jpeg_bytes(p.latest_frame)
    return Response(content=jpg, media_type="image/jpeg")


@app.get("/api/stream/{source_id}")
def stream(request: Request, source_id: str):
    """Low-latency MJPEG stream. Point a browser <img src="/api/stream/{id}"> at it."""
    import time as _time

    m = _mgr()
    p = m.pipelines.get(source_id)
    if p is None or not _can_see_source(request, source_id):
        raise HTTPException(status_code=404, detail="unknown source")

    def gen():
        crlf = b"\x0d\x0a"
        while True:
            if p.latest_frame is not None:
                jpg = frame_to_jpeg_bytes(p.latest_frame)
                if jpg:
                    yield b"--frame" + crlf + b"Content-Type: image/jpeg" + crlf + crlf + jpg + crlf
            _time.sleep(0.1)  # ~10 fps

    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/api/events")
def events(request: Request, limit: int = 100, camera_id: str | None = None, event_type: str | None = None, order: str = "DESC"):
    return _mgr().store.list_events(limit=limit, camera_id=camera_id, event_type=event_type, order=order, tenant_id=_req_tenant(request))


@app.get("/api/clips/{event_id}")
def clip(request: Request, event_id: int):
    ev = _event_for_tenant(request, event_id)
    if ev is None or not ev.get("clip_path"):
        raise HTTPException(status_code=404, detail="no clip for event")
    ref = ev["clip_path"]
    storage = get_storage(_mgr().cfg)
    if storage.provider == "s3":
        return RedirectResponse(storage.url(ref))
    p = Path(ref)
    if not p.exists():
        raise HTTPException(status_code=404, detail="clip file missing")
    return FileResponse(p)


@app.get("/api/thumbs/{event_id}")
def thumb(request: Request, event_id: int):
    ev = _event_for_tenant(request, event_id)
    if ev is None or not ev.get("thumb_path"):
        raise HTTPException(status_code=404, detail="no thumbnail for event")
    ref = ev["thumb_path"]
    storage = get_storage(_mgr().cfg)
    if storage.provider == "s3":
        return RedirectResponse(storage.url(ref))
    p = Path(ref)
    if not p.exists():
        raise HTTPException(status_code=404, detail="thumbnail file missing")
    return FileResponse(p)


@app.get("/api/plates")
def plates(request: Request, limit: int = 100):
    return _mgr().store.list_plates(limit=limit, tenant_id=_req_tenant(request))


@app.get("/api/faces")
def faces(request: Request):
    return _mgr().store.list_faces(tenant_id=_req_tenant(request))


@app.get("/api/face_matches")
def face_matches(request: Request, limit: int = 100):
    return _mgr().store.list_face_matches(limit=limit, tenant_id=_req_tenant(request))


@app.get("/api/identities")
def identities(request: Request):
    return _mgr().store.list_identities(tenant_id=_req_tenant(request))


@app.get("/api/sightings/{identity_id}")
def sightings(request: Request, identity_id: int):
    return _mgr().store.list_sightings(identity_id, tenant_id=_req_tenant(request))


# -- config ------------------------------------------------------------
@app.get("/api/config")
def get_config(request: Request):
    """Read the configuration.

    It carries provider keys, S3 credentials and the file-encryption key, so it is not
    readable by every signed-in user - only by the roles that can also change it.
    ponytail: secrets still come back intact because the Settings screen round-trips the
    whole object; redacting them needs merge-on-save first or a save would wipe them.
    """
    _require_role(request, "admin", "manager")
    return config_to_dict(_mgr().cfg)


@app.put("/api/config")
def put_config(request: Request, data: dict):
    _require_role(request, "admin", "manager")
    from .config import save_config

    cfg = config_from_dict(data)
    save_config(cfg)
    return {"ok": True, "restart_required": True}


# -- search + analytics -------------------------------------------------
@app.get("/api/search")
def search(request: Request, q: str, camera_id: str | None = None, limit: int = 50):
    m = _mgr()
    return SmartSearch(m.store, m.detector.names).run(q, limit=limit, camera_id=camera_id, tenant_id=_req_tenant(request))


@app.get("/api/class_names")
def class_names():
    return _mgr().detector.names


@app.get("/api/zones/{source_id}")
def zones(request: Request, source_id: str):
    m = _mgr()
    p = m.pipelines.get(source_id)
    if p is None or not _can_see_source(request, source_id):
        raise HTTPException(status_code=404, detail="unknown source")
    return p.stats.get("zones", [])


@app.get("/api/heatmap/{source_id}")
def heatmap(request: Request, source_id: str):
    import os
    import tempfile

    m = _mgr()
    p = m.pipelines.get(source_id)
    if p is None or not _can_see_source(request, source_id):
        raise HTTPException(status_code=404, detail="unknown source")
    tmp = tempfile.mktemp(suffix=".png")
    out = p.heatmap.render(tmp)
    with open(out, "rb") as f:
        data = f.read()
    os.remove(out)
    return Response(content=data, media_type="image/png")


@app.get("/api/count")
def count(request: Request):
    return {"events": _mgr().store.count_events(tenant_id=_req_tenant(request))}


@app.get("/api/occupancy")
def occupancy():
    return _mgr().occupancy()


@app.get("/api/occupancy_history")
def occupancy_history(request: Request, since: float | None = None, limit: int = 2000):
    return _mgr().store.list_occupancy_samples(since=since, limit=limit, tenant_id=_req_tenant(request))


# -- embedding (for register flows) ------------------------------------
def _decode_image(data: bytes):
    import io as _io

    import numpy as np
    from PIL import Image

    return np.array(Image.open(_io.BytesIO(data)).convert("RGB"))


@app.post("/api/embed_face")
def embed_face(image: UploadFile = File(...)):
    if _mgr().face_engine is None:
        raise HTTPException(status_code=503, detail="face recognition not available in cloud-only mode")
    img = _decode_image(image.file.read())
    faces = _mgr().face_engine.detect_and_embed(img)
    return [{"embedding": f["embedding"].tolist(), "box": f["box"]} for f in faces]


@app.post("/api/embed_reid")
def embed_reid(image: UploadFile = File(...)):
    if _mgr().reid_engine is None:
        raise HTTPException(status_code=503, detail="re-identification not available in cloud-only mode")
    img = _decode_image(image.file.read())
    emb = _mgr().reid_engine.embed(img[:, :, ::-1])  # RGB -> BGR (reid expects BGR)
    return {"embedding": emb.tolist() if emb is not None else None}


# -- sources -----------------------------------------------------------
@app.post("/api/sources")
def add_source(request: Request, data: dict):
    _require_role(request, "admin", "manager")
    from .config import SourceConfig

    src = SourceConfig(
        id=data.get("id", ""), name=data.get("name", ""), uri=data.get("uri", "0"),
        enabled=bool(data.get("enabled", True)), loop=bool(data.get("loop", True)),
        fast=bool(data.get("fast", False)),
    )
    return {"id": _mgr().add_source(src)}


@app.delete("/api/sources/{source_id}")
def remove_source(request: Request, source_id: str):
    _require_role(request, "admin", "manager")
    _mgr().remove_source(source_id)
    return {"ok": True}


@app.post("/api/upload")
async def upload_video(request: Request, file: UploadFile = File(...)):
    _require_role(request, "admin", "manager")
    up_dir = _mgr().cfg.data_dir / "uploads"
    up_dir.mkdir(parents=True, exist_ok=True)
    name = os.path.basename(file.filename or "upload.mp4")
    dest = up_dir / name
    if dest.exists():
        dest = up_dir / (dest.stem + "_" + str(int(time.time())) + dest.suffix)
    await _write_capped(file, dest)
    return {"path": str(dest), "filename": dest.name}


# -- faces + identities (write) ----------------------------------------
@app.post("/api/faces")
def add_face(request: Request, data: dict):
    _require_role(request, "admin", "manager")
    return {"id": _mgr().store.add_face(data.get("name", ""), data.get("role", ""), data.get("embedding", []), data.get("thumb_path"))}


@app.delete("/api/faces/{face_id}")
def delete_face(request: Request, face_id: int):
    _require_role(request, "admin", "manager")
    if not any(f["id"] == face_id for f in _mgr().store.list_faces(_req_tenant(request))):
        raise HTTPException(status_code=404, detail="face not found")
    _mgr().store.delete_face(face_id)
    return {"ok": True}


@app.post("/api/delete_person")
def delete_person(request: Request, data: dict):
    _require_role(request, "admin")
    face_id = data.get("face_id")
    name = data.get("name")
    # Resolve the face inside the caller's tenant first: store.delete_person matches on a
    # bare name or id and would otherwise wipe another tenant's record.
    owned = [f["id"] for f in _mgr().store.list_faces(_req_tenant(request))
             if f["id"] == face_id or (face_id is None and f.get("name") == name)]
    if not owned:
        raise HTTPException(status_code=404, detail="person not found")
    _mgr().store.delete_person(face_id=owned[0])
    return {"ok": True}


@app.post("/api/identities")
def add_identity(request: Request, data: dict):
    _require_role(request, "admin", "manager")
    return {"id": _mgr().store.add_identity(data.get("name", ""), data.get("face_id"), data.get("embedding", []), data.get("thumb_path"))}


@app.delete("/api/identities/{identity_id}")
def delete_identity(request: Request, identity_id: int):
    _require_role(request, "admin", "manager")
    if not any(i["id"] == identity_id for i in _mgr().store.list_identities(_req_tenant(request))):
        raise HTTPException(status_code=404, detail="identity not found")
    _mgr().store.delete_identity(identity_id)
    return {"ok": True}


# -- live event feed (WebSocket) ---------------------------------------
def _ws_token(websocket: WebSocket) -> tuple[str, str | None]:
    """Read the access token from a 'bearer' subprotocol, falling back to the query string.

    A browser cannot set an Authorization header on a WebSocket, so the token used to be
    query-string only - which writes it into every proxy and access log along the way.
    Offering it as a subprotocol keeps it out of the URL; the query string still works so
    a client that has not been rebuilt yet keeps connecting.
    """
    parts = [p.strip() for p in websocket.headers.get("sec-websocket-protocol", "").split(",")]
    if len(parts) == 2 and parts[0] == "bearer":
        return parts[1], "bearer"
    return websocket.query_params.get("token", ""), None


@app.websocket("/ws/events")
async def ws_events(websocket: WebSocket):
    token, subprotocol = _ws_token(websocket)
    payload = read_token(token, _get_secret(), ACCESS_TOKEN_MAX_AGE) if token else None
    if payload is None or payload.get("typ") != "access":
        await websocket.close(code=1008)
        return
    await websocket.accept(subprotocol=subprotocol)
    last_id = 0
    try:
        while True:
            latest = _mgr().store.list_events(limit=1, tenant_id=payload.get("tenant_id"))
            eid = latest[0]["id"] if latest else 0
            if eid > last_id:
                last_id = eid
                if latest:
                    await websocket.send_json(latest[0])
            await asyncio.sleep(1)
    except Exception:
        pass


@app.get("/api/webrtc/config")
def webrtc_config(request: Request):
    from .webrtc import available, ice_server_dicts

    wcfg = _mgr().cfg.webrtc
    enabled = bool(getattr(wcfg, "enabled", True) and available())
    return {"enabled": enabled, "ice_servers": ice_server_dicts(wcfg) if enabled else []}


@app.websocket("/ws/webrtc/{source_id}")
async def ws_webrtc(websocket: WebSocket, source_id: str):
    token, subprotocol = _ws_token(websocket)
    payload = read_token(token, _get_secret(), ACCESS_TOKEN_MAX_AGE) if token else None
    if payload is None or payload.get("typ") != "access":
        await websocket.close(code=1008)
        return
    p = _mgr().pipelines.get(source_id)
    if p is None or not _tenant_can_see_source(payload.get("tenant_id"), source_id):
        await websocket.close(code=1008)
        return
    from .webrtc import available, make_configuration, make_track

    wcfg = _mgr().cfg.webrtc
    if not getattr(wcfg, "enabled", True):
        await websocket.accept(subprotocol=subprotocol)
        await websocket.send_json({"type": "error", "error": "webrtc disabled"})
        await websocket.close()
        return
    if not available():
        await websocket.accept(subprotocol=subprotocol)
        await websocket.send_json({"type": "error", "error": "aiortc not installed"})
        await websocket.close()
        return

    from aiortc import RTCIceCandidate, RTCPeerConnection, RTCSessionDescription
    from aiortc.contrib.media import MediaRelay

    await websocket.accept(subprotocol=subprotocol)
    pc = RTCPeerConnection(configuration=make_configuration(wcfg))
    relay = MediaRelay()
    pc.addTrack(relay.subscribe(make_track(p)))

    @pc.on("icecandidate")
    async def _on_ice(candidate):
        if candidate:
            await websocket.send_json({
                "type": "candidate",
                "candidate": candidate.candidate,
                "sdpMid": candidate.sdpMid,
                "sdpMLineIndex": candidate.sdpMLineIndex,
            })

    try:
        while True:
            msg = await websocket.receive_json()
            kind = msg.get("type")
            if kind == "offer":
                offer = RTCSessionDescription(sdp=msg.get("sdp", ""), type="offer")
                await pc.setRemoteDescription(offer)
                answer = await pc.createAnswer()
                await pc.setLocalDescription(answer)
                await websocket.send_json({
                    "type": "answer",
                    "sdp": pc.localDescription.sdp,
                    "sdpType": pc.localDescription.type,
                })
            elif kind == "candidate":
                await pc.addIceCandidate(RTCIceCandidate(
                    sdpMid=msg.get("sdpMid"),
                    sdpMLineIndex=msg.get("sdpMLineIndex"),
                    candidate=msg.get("candidate"),
                ))
    except Exception as exc:
        log.info("webrtc session ended for %s: %s", source_id, exc)
    finally:
        await pc.close()


# -- open alerts ------------------------------------------------------
@app.get("/api/open_alerts")
def open_alerts(request: Request, limit: int = 200):
    return _mgr().store.list_open_alerts(limit=limit, tenant_id=_req_tenant(request))


@app.post("/api/escalate/{event_id}")
def escalate(request: Request, event_id: int):
    _require_role(request, "admin", "security", "manager")
    if _event_for_tenant(request, event_id) is None:
        raise HTTPException(status_code=404, detail="event not found")
    _mgr().store.escalate(event_id)
    return {"ok": True}


# -- alert center ------------------------------------------------------
@app.post("/api/ack/{event_id}")
def ack(request: Request, event_id: int):
    _require_role(request, "admin", "security", "manager")
    if _event_for_tenant(request, event_id) is None:
        raise HTTPException(status_code=404, detail="event not found")
    _mgr().store.acknowledge(event_id)
    return {"ok": True}


@app.post("/api/resolve/{event_id}")
def resolve(request: Request, event_id: int):
    _require_role(request, "admin", "security", "manager")
    if _event_for_tenant(request, event_id) is None:
        raise HTTPException(status_code=404, detail="event not found")
    _mgr().store.resolve(event_id)
    return {"ok": True}


@app.post("/api/assign/{event_id}")
def assign(request: Request, event_id: int, data: dict):
    _require_role(request, "admin", "security", "manager")
    if _event_for_tenant(request, event_id) is None:
        raise HTTPException(status_code=404, detail="event not found")
    _mgr().store.assign(event_id, data.get("user", ""))
    return {"ok": True}
