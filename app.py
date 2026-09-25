r"""SmartCam dashboard (Streamlit).

Run with:
    .venv\Scripts\python -m streamlit run app.py
"""
from __future__ import annotations

import datetime as _dt
import os
import time
from pathlib import Path

import numpy as np
import streamlit as st

from smartcam.analytics import build_report
from smartcam.audit import audit_log
from smartcam.auth import authenticate
from smartcam.config import ROOT, SourceConfig, ZoneConfig, hash_password, load_config, save_config
from smartcam.pipeline import PipelineManager
from smartcam.search import SmartSearch
from smartcam.utils import extract_frame, format_duration, save_thumbnail, setup_logging, ts_to_iso

setup_logging(ROOT / "data")
st.set_page_config(page_title="SmartCam", page_icon="🎥", layout="wide")

EVENT_ICONS = {
    "detection": "🎯", "loitering": "🚶", "intrusion": "🚨", "queue": "👥",
    "fall": "🆘", "abandoned": "🧳", "parking": "🚗",
}
SESSION_TIMEOUT_SEC = 8 * 3600


@st.cache_resource
def get_manager():
    api_url = os.environ.get("SMART_CAM_API_URL", "")
    if api_url:
        from smartcam.client import ApiClient

        return ApiClient(api_url)
    return PipelineManager(load_config())


def _rgb(frame: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(frame[:, :, ::-1])


def _badge(status: str) -> str:
    return {"running": "🟢 Running", "stopped": "⚪ Stopped", "error": "🔴 Error"}.get(status, status)


def _source_name(mgr: PipelineManager, source_id: str) -> str:
    for s in mgr.cfg.sources:
        if s.id == source_id:
            return s.name
    return source_id


def _etype(ev: dict) -> str:
    t = ev.get("event_type") or "detection"
    return EVENT_ICONS.get(t, "📌") + " " + t


def _audit(action: str, detail: str = "") -> None:
    audit_log(ROOT / "data" / "audit.log", st.session_state.get("role", ""), action, detail)


def _beep_html() -> str:
    import base64
    import io
    import math
    import struct
    import wave

    sr = 8000
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"".join(struct.pack("<h", int(2500 * math.sin(2 * math.pi * 880 * i / sr))) for i in range(int(sr * 0.25))))
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f'<audio autoplay><source src="data:audio/wav;base64,{b64}" type="audio/wav"></audio>'


# --------------------------------------------------------------------------- #
# Login
# --------------------------------------------------------------------------- #
def render_login(cfg) -> None:
    st.title("🎥 SmartCam")
    st.markdown("Please sign in to access the dashboard.")
    with st.form("login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Sign in"):
            role = None
            if os.environ.get("SMART_CAM_API_URL", ""):
                from smartcam.client import ApiClient
                c = ApiClient(os.environ["SMART_CAM_API_URL"])
                role = c.login(username, password)
                if role:
                    st.session_state["api_token"] = c._token
            else:
                role = authenticate(cfg.auth, username, password)
            if role:
                st.session_state["role"] = role
                st.session_state["user"] = username
                st.session_state["login_ts"] = time.time()
                _audit("login", username)
                st.rerun()
            else:
                audit_log(ROOT / "data" / "audit.log", "-", "login_failed", username)
                st.error("Invalid username or password.")


# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
def render_sidebar(mgr: PipelineManager, role: str) -> str:
    st.sidebar.title("🎥 SmartCam")
    st.sidebar.caption("YOLOv8 smart security platform")
    if role:
        st.sidebar.caption("Signed in as **" + role + "**")
        if st.sidebar.button("Log out", width="stretch"):
            _audit("logout")
            st.session_state.clear()
            st.rerun()

    source_ids = [s.id for s in mgr.cfg.sources]
    source_id = st.sidebar.selectbox("Camera / source", source_ids, format_func=lambda i: _source_name(mgr, i))
    p = mgr.pipelines[source_id]
    st.sidebar.markdown("**Status:** " + _badge(p.stats["status"]))
    h = p.health() if hasattr(p, "health") else None
    if h == "offline":
        st.sidebar.error("⚠ Camera offline")
    elif h == "stalled":
        st.sidebar.warning("⚠ Camera stalled (no frames)")

    if role != "viewer":
        c1, c2 = st.sidebar.columns(2)
        if c1.button("▶ Start", width="stretch"):
            p.start()
            _audit("start", source_id)
        if c2.button("⏹ Stop", width="stretch"):
            p.stop()
            _audit("stop", source_id)

    st.sidebar.markdown("---")
    st.sidebar.subheader("Detection (live)")
    d = mgr.cfg.detection
    d.conf = st.sidebar.slider("Confidence", 0.05, 0.95, float(d.conf), 0.05)
    d.iou = st.sidebar.slider("IoU", 0.1, 0.9, float(d.iou), 0.05)
    d.frame_stride = st.sidebar.slider("Frame stride", 1, 10, int(d.frame_stride))
    st.sidebar.caption("Changes apply to the running pipeline immediately.")
    return source_id


# --------------------------------------------------------------------------- #
# Live monitor
# --------------------------------------------------------------------------- #
@st.fragment(run_every=1.0)
def live_feed(mgr: PipelineManager, source_id: str) -> None:
    p = mgr.pipelines[source_id]
    frame = p.latest_frame
    stats = p.stats

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Status", _badge(stats["status"]))
    m2.metric("FPS", str(stats["fps"]))
    m3.metric("Frames", str(stats["frames"]))
    m4.metric("Objects", ", ".join(stats["active_objects"]) if stats["active_objects"] else "—")

    if frame is not None:
        st.image(_rgb(frame), width="stretch", channels="RGB")
    else:
        st.info("No frame yet. Press Start to begin processing this source.")
    if stats.get("error"):
        st.error(stats["error"])


@st.fragment(run_every=1.0)
def live_grid(mgr: PipelineManager) -> None:
    cols = st.columns(len(mgr.cfg.sources))
    for i, s in enumerate(mgr.cfg.sources):
        with cols[i]:
            p = mgr.pipelines[s.id]
            st.markdown("**" + s.name + "**")
            if p.latest_frame is not None:
                st.image(_rgb(p.latest_frame), width="stretch", channels="RGB")
            else:
                st.info("no frame")
            st.caption(_badge(p.stats["status"]) + " · " + str(p.stats["fps"]) + " fps")


@st.fragment(run_every=2.0)
def live_events_feed(mgr: PipelineManager) -> None:
    events = mgr.store.list_events(limit=5)
    if events:
        st.markdown("**🔴 Latest events**")
        for ev in events:
            st.markdown("- " + _etype(ev) + " · " + ", ".join(ev.get("objects") or []) + " · " + ts_to_iso(ev.get("start_ts")))


def render_live(mgr: PipelineManager, source_id: str) -> None:
    st.subheader("Live monitoring")
    grid = st.checkbox("Grid view (all cameras)")
    if grid:
        live_grid(mgr)
        return
    idx = [s.id for s in mgr.cfg.sources].index(source_id)
    st.caption("Source URI: " + str(mgr.cfg.sources[idx].uri))
    live_feed(mgr, source_id)
    live_events_feed(mgr)


# --------------------------------------------------------------------------- #
# New-event alert (toast + sound)
# --------------------------------------------------------------------------- #
@st.fragment(run_every=2.0)
def alert_watch(mgr: PipelineManager) -> None:
    latest = mgr.store.list_events(limit=1)
    eid = latest[0]["id"] if latest else 0
    prev = st.session_state.get("_last_seen_event", eid)
    if eid > prev:
        st.session_state["_last_seen_event"] = eid
        if latest:
            st.toast("New event: " + _etype(latest[0]) + " (#" + str(eid) + ")")
            st.html(_beep_html())


# --------------------------------------------------------------------------- #
# Shared event card
# --------------------------------------------------------------------------- #
def event_card(ev: dict, key_prefix: str = "ev") -> None:
    with st.container(border=True):
        c1, c2 = st.columns([1, 3])
        with c1:
            if ev.get("thumb_path"):
                st.image(ev["thumb_path"], width="stretch")
            else:
                st.markdown("🖼️ *no thumbnail*")
        with c2:
            objs = ev.get("objects") or []
            label = ", ".join(objs) if objs else "motion"
            st.markdown("**" + _etype(ev) + "** · #" + str(ev["id"]) + " — " + label + " · " + format_duration(ev.get("duration")))
            cam = ev.get("camera_name") or ev.get("camera_id")
            st.caption("📍 " + str(cam) + " · 🕒 " + ts_to_iso(ev.get("start_ts")))
            if ev.get("summary"):
                st.markdown("📝 " + str(ev["summary"]))
            if ev.get("plate"):
                st.markdown("🚗 Plate: **" + str(ev["plate"]) + "**")
            bits = []
            if ev.get("escalated"):
                bits.append("🚨 ESCALATED")
            if ev.get("acknowledged"):
                bits.append("✅ acknowledged")
            if ev.get("resolved"):
                bits.append("✔ resolved")
            if ev.get("assignee"):
                bits.append("👤 " + str(ev["assignee"]))
            if bits:
                st.caption(" · ".join(bits))
            if ev.get("clip_path"):
                with st.expander("▶ Play clip"):
                    st.video(ev["clip_path"])
                    dur = ev.get("duration") or 0
                    if dur and dur > 0:
                        sec = st.slider("Scrub", 0.0, float(dur), 0.0, 0.5, key=key_prefix + "_scrub_" + str(ev["id"]))
                        fr = extract_frame(ev["clip_path"], sec)
                        if fr is not None:
                            st.image(_rgb(fr), width="stretch", channels="RGB")
                from pathlib import Path

                cp = Path(ev["clip_path"])
                if cp.exists() and cp.stat().st_size < 50 * 1024 * 1024:
                    try:
                        st.download_button(
                            "⬇ Download clip", data=cp.read_bytes(), file_name=cp.name,
                            mime="video/mp4", key=key_prefix + "_dl_" + str(ev["id"]),
                        )
                    except OSError:
                        pass


# --------------------------------------------------------------------------- #
# Alerts
# --------------------------------------------------------------------------- #
def render_alerts(mgr: PipelineManager) -> None:
    st.subheader("Alerts")
    open_alerts = mgr.store.list_open_alerts(limit=200)
    if not open_alerts:
        st.success("✅ No open alerts.")
        return
    users = [u.username for u in mgr.cfg.auth.users] or ["security"]
    st.caption(str(len(open_alerts)) + " open alert(s)")
    for ev in open_alerts:
        event_card(ev, "al")
        c1, c2, c3, c4 = st.columns([1, 1, 2, 1])
        if c1.button("✅ Ack", key="al_ack_" + str(ev["id"])):
            mgr.store.acknowledge(ev["id"])
            _audit("ack", str(ev["id"]))
            st.rerun()
        if c2.button("✔ Resolve", key="al_res_" + str(ev["id"])):
            mgr.store.resolve(ev["id"])
            _audit("resolve", str(ev["id"]))
            st.rerun()
        who = c3.selectbox("Assign to", users, key="al_asn_" + str(ev["id"]))
        if c4.button("Assign", key="al_asnb_" + str(ev["id"])):
            mgr.store.assign(ev["id"], who)
            _audit("assign", str(ev["id"]))
            st.rerun()


# --------------------------------------------------------------------------- #
# Events
# --------------------------------------------------------------------------- #
def render_events(mgr: PipelineManager) -> None:
    st.subheader("Event clips")
    cams = [s.id for s in mgr.cfg.sources]
    types = sorted({e.get("event_type") or "detection" for e in mgr.store.list_events(limit=1000)})

    f1, f2, f3 = st.columns(3)
    cam_sel = f1.selectbox("Camera", ["all"] + cams, format_func=lambda i: "All" if i == "all" else _source_name(mgr, i))
    type_sel = f2.selectbox("Type", ["all"] + types)
    dr = f3.date_input("Date range", value=(_dt.date.today() - _dt.timedelta(days=7), _dt.date.today()))

    since = until = None
    if isinstance(dr, (list, tuple)) and len(dr) == 2:
        since = _dt.datetime.combine(dr[0], _dt.time.min).timestamp()
        until = _dt.datetime.combine(dr[1], _dt.time.max).timestamp()

    open_only = st.checkbox("Open alerts only (unresolved)")
    events = mgr.store.list_events(
        limit=100, camera_id=None if cam_sel == "all" else cam_sel,
        since=since, until=until, event_type=None if type_sel == "all" else type_sel,
    )
    if open_only:
        events = [e for e in events if not e.get("resolved")]
    if not events:
        st.info("No events match. Start a pipeline; events appear automatically.")
        return
    st.caption(str(len(events)) + " matching events")
    for ev in events:
        event_card(ev)
        if not ev.get("resolved"):
            b1, b2 = st.columns(2)
            if b1.button("✅ Acknowledge", key="ack_" + str(ev["id"])):
                mgr.store.acknowledge(ev["id"])
                _audit("ack", str(ev["id"]))
                st.rerun()
            if b2.button("✔ Resolve", key="res_" + str(ev["id"])):
                mgr.store.resolve(ev["id"])
                _audit("resolve", str(ev["id"]))
                st.rerun()


# --------------------------------------------------------------------------- #
# Import / upload video
# --------------------------------------------------------------------------- #
def _sanitize_filename(name: str) -> str:
    name = "".join(ch for ch in name if ch.isalnum() or ch in "._- ")
    return name or "video.mp4"


@st.fragment(run_every=1.0)
def _assessment_fragment(mgr: PipelineManager, p, sid: str) -> None:
    stats = p.stats
    if stats["frames"] == 0:
        st.info("Warming up the model — the live detection view will appear here…")
        return
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Status", _badge(stats["status"]))
    m2.metric("Frames", str(stats["frames"]))
    m3.metric("FPS", str(stats["fps"]))
    m4.metric("Objects", ", ".join(stats["active_objects"]) if stats["active_objects"] else "—")

    if p.latest_frame is not None:
        st.image(_rgb(p.latest_frame), width="stretch", channels="RGB")

    if stats["status"] == "stopped":
        st.success("✅ Assessment complete")
        events = mgr.store.list_events(limit=50, camera_id=sid)
        st.write("Found **" + str(len(events)) + "** event(s):")
        for ev in events[:10]:
            st.markdown("- " + _etype(ev) + " · " + ", ".join(ev.get("objects") or []) + " · " + ts_to_iso(ev.get("start_ts")))
        st.caption("View clips and download in the Events tab.")


def render_import(mgr: PipelineManager) -> None:
    st.subheader("Import video for assessment")
    sid = st.session_state.get("_assessment_sid")
    p = mgr.pipelines.get(sid) if sid else None

    if p is not None:
        st.caption("Assessing: " + p.source.name)
        b1, b2 = st.columns([1, 1])
        if b1.button("← New import", width="stretch"):
            st.session_state.pop("_assessment_sid", None)
            st.rerun()
        if b2.button("🗑 Remove this video", width="stretch"):
            mgr.remove_source(sid)
            st.session_state.pop("_assessment_sid", None)
            try:
                Path(p.source.uri).unlink(missing_ok=True)
            except OSError:
                pass
            st.rerun()
        _assessment_fragment(mgr, p, sid)
        return

    st.caption("Upload a video, then press Enter to analyze it once (detection, events, clips).")
    fast = st.checkbox("⚡ Fast processing (lower resolution, ~3-4x faster)", value=True, key="import_fast")
    up = st.file_uploader("Upload video", type=["mp4", "avi", "mov", "mkv", "webm", "m4v", "mpg", "mpeg"], key="video_uploader")
    if up is not None:
        name = _sanitize_filename(up.name)
        c1, c2 = st.columns([4, 1])
        c1.write("**" + name + "** · " + f"{up.size / 1e6:.1f} MB")
        if c2.button("▶ Enter", width="stretch"):
            dest = mgr.cfg.data_dir / "uploads" / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                dest = dest.with_name(f"{int(time.time())}_{name}")
            dest.write_bytes(up.getvalue())
            nid = f"upload_{int(time.time())}"
            src = SourceConfig(id=nid, name="Upload: " + name, uri=str(dest), enabled=True, loop=False, fast=fast)
            mgr.add_source(src)
            mgr.start(nid)
            st.session_state["_assessment_sid"] = nid
            _audit("upload", name)
            st.rerun()

    uploaded = [s for s in mgr.cfg.sources if s.id.startswith("upload_")]
    if uploaded:
        st.markdown("### Uploaded assessments")
        for s in uploaded:
            q = mgr.pipelines.get(s.id)
            status = _badge(q.stats["status"]) if q else "—"
            c1, c2 = st.columns([4, 1])
            c1.markdown("**" + s.name + "** · " + status)
            if c2.button("Remove", key="rm_" + s.id):
                mgr.remove_source(s.id)
                try:
                    Path(s.uri).unlink(missing_ok=True)
                except OSError:
                    pass
                st.rerun()


# --------------------------------------------------------------------------- #
# Smart search
# --------------------------------------------------------------------------- #
def render_search(mgr: PipelineManager) -> None:
    st.subheader("Smart search")
    cams = [s.id for s in mgr.cfg.sources]
    cam_sel = st.selectbox("Camera", ["all"] + cams, format_func=lambda i: "All" if i == "all" else _source_name(mgr, i), key="search_cam")
    q = st.text_input("Search events", placeholder="e.g. 'person at night', 'car yesterday', 'LND123AB'")
    if not q:
        st.info("Queries can mix objects, time-of-day, dates, and plate numbers.")
        return

    from smartcam.alpr import _is_plate
    import re as _re

    plate_like = any(_is_plate(_re.sub(r"[^A-Z0-9]", "", w.upper())) for w in q.split())
    if plate_like:
        plates = mgr.store.search_plates(q, limit=20)
        if plates:
            st.markdown("### 🚗 Matching plates")
            for pl in plates:
                with st.container(border=True):
                    c1, c2 = st.columns([1, 4])
                    with c1:
                        if pl.get("crop_path"):
                            st.image(pl["crop_path"], width="stretch")
                    with c2:
                        conf = pl.get("confidence")
                        conf_txt = "{:.0%}".format(conf) if conf is not None else ""
                        head = "**" + pl["plate"] + "**"
                        if conf_txt:
                            head += " · " + conf_txt
                        st.markdown(head)
                        st.caption("📍 " + str(pl.get("camera_name") or pl.get("camera_id")) + " · 🕒 " + ts_to_iso(pl.get("ts")))

    results = mgr.search(q, limit=50, camera_id=None if cam_sel == "all" else cam_sel)
    st.caption(str(len(results)) + " event result(s) for: " + q)
    for ev in results:
        event_card(ev, "sr")


# --------------------------------------------------------------------------- #
# Plates (ANPR)
# --------------------------------------------------------------------------- #
def render_plates(mgr: PipelineManager) -> None:
    st.subheader("Vehicle plates (ANPR)")
    q = st.text_input("Search plate", placeholder="e.g. LND123AB")
    if q:
        rows = mgr.store.search_plates(q, limit=100)
        st.caption(str(len(rows)) + " plate(s) matching: " + q)
    else:
        rows = mgr.store.list_plates(limit=100)
        st.caption("Latest " + str(len(rows)) + " plates read")
    if not rows:
        st.info("No plates yet. Enable ALPR in Settings and detect a vehicle in a parking zone.")
        return
    for pl in rows:
        with st.container(border=True):
            c1, c2 = st.columns([1, 4])
            with c1:
                if pl.get("crop_path"):
                    st.image(pl["crop_path"], width="stretch")
            with c2:
                conf = pl.get("confidence")
                conf_txt = "{:.0%}".format(conf) if conf is not None else ""
                head = "**" + pl["plate"] + "**"
                if conf_txt:
                    head += " · " + conf_txt
                st.markdown(head)
                st.caption("📍 " + str(pl.get("camera_name") or pl.get("camera_id")) + " · 🕒 " + ts_to_iso(pl.get("ts")))


# --------------------------------------------------------------------------- #
# Track person (ReID)
# --------------------------------------------------------------------------- #
def render_reid(mgr: PipelineManager) -> None:
    st.subheader("Track a person across cameras (ReID)")
    if not mgr.cfg.reid.enabled:
        st.warning("ReID is disabled. Enable it in Settings (and install torchreid).")
    identities = mgr.store.list_identities()
    if identities:
        sel = st.selectbox("Person", identities, format_func=lambda i: i["name"])
        sightings = sorted(mgr.store.list_sightings(sel["id"]), key=lambda x: x["ts"])
        if sightings:
            st.markdown("### Movement timeline for **" + sel["name"] + "**")
            path = " → ".join((s.get("camera_name") or s.get("camera_id") or "?") for s in sightings)
            st.caption(path)
            for s in sightings:
                with st.container(border=True):
                    c1, c2 = st.columns([1, 4])
                    with c1:
                        if s.get("thumb_path"):
                            st.image(s["thumb_path"], width="stretch")
                    with c2:
                        conf = s.get("confidence")
                        conf_txt = "{:.0%}".format(conf) if conf is not None else ""
                        head = "📍 " + str(s.get("camera_name") or s.get("camera_id")) + " · 🕒 " + ts_to_iso(s.get("ts"))
                        if conf_txt:
                            head += " · " + conf_txt
                        st.markdown(head)
        else:
            st.info("No sightings yet for " + sel["name"] + ".")
    else:
        st.info("No tracked identities yet. Create one below, or let face recognition anchor one automatically.")
    st.markdown("### Register a person to track")
    up = st.file_uploader("Person photo", type=["jpg", "jpeg", "png"], key="reid_reg")
    name = st.text_input("Name", key="reid_name")
    if up is not None and name and st.button("Track this person"):
        img = _read_image(up)
        try:
            emb = mgr.reid_engine.embed(img)
        except Exception as exc:
            st.error("ReID engine error (is torchreid installed?): " + str(exc))
            return
        if emb is None:
            st.error("Could not embed the photo.")
            return
        thumb = save_thumbnail(img, mgr.cfg.thumbs_dir / ("ident_" + name + ".jpg"))
        mgr.store.add_identity(name, None, emb, str(thumb))
        st.success("Registered " + name)
        st.rerun()


# --------------------------------------------------------------------------- #
# Faces (recognition)
# --------------------------------------------------------------------------- #
def render_faces(mgr: PipelineManager) -> None:
    st.subheader("Face recognition")
    if not mgr.cfg.face.enabled:
        st.warning("Face recognition is disabled. Enable it in Settings (and install deepface).")
    a, b, c = st.tabs(["Register", "Search", "Matches"])
    with a:
        _render_face_register(mgr)
    with b:
        _render_face_search(mgr)
    with c:
        _render_face_matches(mgr)


def _read_image(up):
    import io

    from PIL import Image

    return np.array(Image.open(io.BytesIO(up.getvalue())).convert("RGB"))


def _render_face_register(mgr: PipelineManager) -> None:
    st.markdown("Register a known face (staff, VIP, banned, ...).")
    up = st.file_uploader("Face photo", type=["jpg", "jpeg", "png"], key="face_reg")
    name = st.text_input("Name", key="face_name")
    role = st.selectbox("Role", ["staff", "vip", "guest", "banned"], key="face_role")
    consent = st.checkbox("I have consent to store this person's face data", key="face_consent")
    if up is not None and name and st.button("Register face"):
        img = _read_image(up)
        try:
            faces = mgr.face_engine.detect_and_embed(img)
        except Exception as exc:
            st.error("Face engine error (is deepface installed?): " + str(exc))
            return
        if not faces:
            st.error("No face detected in the photo.")
            return
        emb = faces[0]["embedding"]
        x1, y1, x2, y2 = [int(v) for v in faces[0]["box"]]
        crop = img[max(0, y1):y2, max(0, x1):x2]
        thumb = save_thumbnail(crop, mgr.cfg.thumbs_dir / ("registered_" + name + ".jpg")) if crop.size else None
        mgr.store.add_face(name, role, emb, str(thumb) if thumb else None, consent=1 if consent else 0)
        st.success("Registered " + name)
        st.rerun()
    faces = mgr.store.list_faces()
    if faces:
        st.markdown("### Registered faces")
        for f in faces:
            c1, c2 = st.columns([4, 1])
            consent_txt = " · ✔ consent" if f.get("consent") else " · ✘ no consent"
            c1.markdown("**" + f["name"] + "** · " + str(f.get("role", "")) + consent_txt)
            if c2.button("Delete person's data", key="delperson_" + str(f["id"])):
                mgr.store.delete_person(face_id=f["id"])
                _audit("delete_person", str(f["name"]))
                st.rerun()


def _render_face_search(mgr: PipelineManager) -> None:
    st.markdown("Find every appearance of a face across cameras.")
    up = st.file_uploader("Query face photo", type=["jpg", "jpeg", "png"], key="face_q")
    if up is not None and st.button("Search appearances"):
        img = _read_image(up)
        try:
            faces = mgr.face_engine.detect_and_embed(img)
        except Exception as exc:
            st.error("Face engine error: " + str(exc))
            return
        if not faces:
            st.error("No face detected.")
            return
        q_emb = faces[0]["embedding"]
        scored = []
        for m in mgr.store.list_face_matches(limit=1000):
            if not m.get("embedding"):
                continue
            s = mgr.face_engine.cosine(q_emb, m["embedding"])
            if s >= mgr.cfg.face.min_conf:
                scored.append((s, m))
        scored.sort(key=lambda x: -x[0])
        st.caption(str(len(scored)) + " appearance(s) found")
        for s, m in scored[:50]:
            with st.container(border=True):
                c1, c2 = st.columns([1, 4])
                with c1:
                    if m.get("thumb_path"):
                        st.image(m["thumb_path"], width="stretch")
                with c2:
                    st.markdown("**" + str(m["name"]) + "** · {:.0%}".format(s))
                    st.caption("📍 " + str(m.get("camera_name") or m.get("camera_id")) + " · 🕒 " + ts_to_iso(m.get("ts")))


def _render_face_matches(mgr: PipelineManager) -> None:
    matches = mgr.store.list_face_matches(limit=100)
    if not matches:
        st.info("No face matches logged yet.")
        return
    st.caption("Latest " + str(len(matches)) + " face detections")
    for m in matches:
        with st.container(border=True):
            c1, c2 = st.columns([1, 4])
            with c1:
                if m.get("thumb_path"):
                    st.image(m["thumb_path"], width="stretch")
            with c2:
                conf = m.get("confidence")
                conf_txt = "{:.0%}".format(conf) if conf is not None else ""
                head = "**" + str(m["name"]) + "**"
                if conf_txt:
                    head += " · " + conf_txt
                st.markdown(head)
                st.caption("📍 " + str(m.get("camera_name") or m.get("camera_id")) + " · 🕒 " + ts_to_iso(m.get("ts")))


# --------------------------------------------------------------------------- #
# Analytics
# --------------------------------------------------------------------------- #
@st.fragment(run_every=2.0)
def occupancy_view(mgr: PipelineManager) -> None:
    o = mgr.occupancy()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👥 People now", o["people"])
    c2.metric("🚗 Vehicles now", o["vehicles"])
    c3.metric("📥 Entered today", o.get("entered", 0))
    c4.metric("📤 Left today", o.get("left", 0))
    if o.get("cameras"):
        st.markdown("**Per camera**")
        for _cid, c in o["cameras"].items():
            st.markdown("- " + c["name"] + ": " + str(c["people"]) + " people · " + str(c["vehicles"]) + " vehicles · " + _badge(c["status"]))


def render_analytics(mgr: PipelineManager, source_id: str) -> None:
    st.subheader("Analytics")
    st.markdown("### System occupancy (all cameras)")
    occupancy_view(mgr)
    p = mgr.pipelines[source_id]

    zones = p.stats.get("zones") or []
    if zones:
        st.markdown("### Zones (live)")
        cols = st.columns(len(zones))
        for i, z in enumerate(zones):
            with cols[i]:
                if z.get("parking"):
                    st.metric(z["name"], f"{z['vehicle_count']}/{z.get('capacity') or '∞'} vehicles")
                else:
                    st.metric(z["name"], f"{z['occupancy']} people")

    st.markdown("### Foot-traffic heatmap")
    if st.button("Render heatmap for this source"):
        out = p.heatmap.render(mgr.cfg.analytics_dir / f"heatmap_{source_id}.png")
        st.image(str(out), width="stretch")

    st.markdown("### Occupancy history (24h)")
    if st.button("Render occupancy chart"):
        from smartcam.analytics import render_occupancy_chart

        since = time.time() - 86400
        samples = mgr.store.list_occupancy_samples(since=since)
        out = render_occupancy_chart(samples, mgr.cfg.analytics_dir / "occupancy.png")
        st.image(str(out), width="stretch")

    st.markdown("### Incident report")
    interval = st.radio("Period", ["daily", "weekly"], horizontal=True)
    since = time.time() - (86400 if interval == "daily" else 7 * 86400)
    rep = build_report(mgr.store, since, interval)
    st.text(rep)
    st.download_button("Download report", rep, file_name=f"smartcam_{interval}_report.txt")


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #
def _parse_list(text: str) -> list:
    return [t.strip() for t in (text or "").split(",") if t.strip()]


def _parse_points(text: str) -> list:
    out = []
    for part in (text or "").replace(" ", "").split(";"):
        if "," in part:
            try:
                x, y = part.split(",")
                out.append([float(x), float(y)])
            except ValueError:
                pass
    return out


def _pts_to_text(points) -> str:
    return "; ".join(str(round(p[0], 3)) + "," + str(round(p[1], 3)) for p in (points or []))


def _zone_draw_canvas(mgr: PipelineManager):
    try:
        from streamlit_drawable_canvas import st_canvas
    except Exception:
        return None
    sources = mgr.cfg.sources
    if not sources:
        return None
    sid = st.selectbox("Draw over camera", [s.id for s in sources], format_func=lambda i: _source_name(mgr, i), key="zone_draw_src")
    p = mgr.pipelines.get(sid)
    frame = p.latest_frame if p else None
    if frame is None:
        st.info("Start this camera to draw zones over its live frame.")
        return None
    bg = _rgb(frame)
    h, w = bg.shape[:2]
    canvas = st_canvas(
        background_image=bg, drawing_mode="polygon", stroke_width=2,
        stroke_color="#ff4b4b", fill_color="rgba(255,75,75,0.25)",
        height=min(480, h), width=min(880, w), key="zone_canvas",
    )
    if canvas.json_data is not None:
        for obj in canvas.json_data.get("objects", []):
            pts = obj.get("path")
            if pts and len(pts) >= 3:
                return [[float(p[0]) / w, float(p[1]) / h] for p in pts]
    return None


def render_settings(mgr: PipelineManager) -> None:
    cfg = mgr.cfg
    st.subheader("Configuration")
    st.caption("Configure every feature, then click Save & restart. File: " + str(ROOT / "config.json"))

    t = st.tabs(["📷 Cameras", "🗺️ Zones", "🎯 Detection", "🎞️ Events", "🤖 AI & ML", "🔒 Security"])
    with t[0]:
        _render_sources(mgr)
    with t[1]:
        _render_zones(mgr)
    with t[2]:
        _render_detection(cfg)
    with t[3]:
        _render_events(cfg)
    with t[4]:
        _render_ai(cfg)
    with t[5]:
        _render_security(cfg)

    if st.button("💾 Save config & restart", width="stretch"):
        mgr.save_config(cfg)
        get_manager.clear()
        _audit("config_save")
        st.success("Config saved. Reloading...")
        st.rerun()


def _render_sources(mgr: PipelineManager) -> None:
    st.markdown("**Cameras / sources**")
    for s in list(mgr.cfg.sources):
        with st.expander(s.name or s.id, expanded=False):
            s.name = st.text_input("Name", s.name, key="src_name_" + s.id)
            s.uri = st.text_input("URI", s.uri, key="src_uri_" + s.id, help="0 = webcam, rtsp://..., http://..., or a video path")
            s.enabled = st.checkbox("Enabled", s.enabled, key="src_en_" + s.id)
            s.loop = st.checkbox("Loop video files", s.loop, key="src_loop_" + s.id)
            if st.button("Remove", key="src_rm_" + s.id):
                mgr.remove_source(s.id)
                st.rerun()
    with st.expander("+ Add camera", expanded=False):
        nid = st.text_input("ID", "camera-2", key="new_src_id")
        nname = st.text_input("Name", "New camera", key="new_src_name")
        nuri = st.text_input("URI", "0", key="new_src_uri")
        if st.button("Add camera"):
            if nid and not any(s.id == nid for s in mgr.cfg.sources):
                mgr.add_source(SourceConfig(id=nid, name=nname or nid, uri=nuri or "0", enabled=True, loop=True))
                st.rerun()
            else:
                st.warning("ID is empty or already exists.")


def _render_zones(mgr: PipelineManager) -> None:
    st.markdown("**Zones** (polygon points are normalized 0..1)")
    for z in list(mgr.cfg.zones):
        with st.expander(z.name or z.id, expanded=False):
            z.name = st.text_input("Name", z.name, key="z_name_" + z.id)
            z.source_id = st.text_input("Source ID (blank = all cameras)", z.source_id, key="z_src_" + z.id)
            z.points = _parse_points(st.text_input("Points (x,y; x,y; ...)", _pts_to_text(z.points), key="z_pts_" + z.id))
            z.classes = _parse_list(st.text_input("Classes (comma)", ", ".join(z.classes), key="z_cls_" + z.id))
            z.max_occupancy = st.number_input("Max occupancy (0 = off)", 0, 200, int(z.max_occupancy or 0), key="z_mo_" + z.id) or None
            z.loiter_sec = st.number_input("Loiter seconds (0 = off)", 0.0, 3600.0, float(z.loiter_sec or 0.0), key="z_lo_" + z.id) or None
            z.restricted = st.checkbox("Restricted zone", z.restricted, key="z_res_" + z.id)
            z.allowed_window = st.text_input("Allowed window (HH:MM-HH:MM)", z.allowed_window, key="z_win_" + z.id)
            z.parking = st.checkbox("Parking zone", z.parking, key="z_park_" + z.id)
            z.capacity = st.number_input("Parking capacity (0 = off)", 0, 500, int(z.capacity or 0), key="z_cap_" + z.id) or None
            if st.button("Remove zone", key="z_rm_" + z.id):
                mgr.cfg.zones.remove(z)
                st.rerun()
    with st.expander("+ Add zone", expanded=False):
        new_name = st.text_input("Name", "Zone", key="new_zone_name")
        new_classes = st.text_input("Classes (comma)", "person", key="new_zone_classes")
        drawn = _zone_draw_canvas(mgr)
        pts_text = st.text_input("Points (x,y; x,y; ...)", key="new_zone_points")
        points = drawn if drawn else _parse_points(pts_text)
        if points and len(points) >= 3:
            st.caption("Zone points: " + _pts_to_text(points))
        if st.button("Add zone"):
            if points and len(points) >= 3:
                zid = "zone_" + str(int(time.time()))
                mgr.cfg.zones.append(ZoneConfig(id=zid, name=new_name or zid, points=points, classes=_parse_list(new_classes)))
                st.rerun()
            else:
                st.warning("Draw a polygon or enter at least 3 points.")


def _render_detection(cfg) -> None:
    st.markdown("**Detection & tracking**")
    cfg.detection.model = st.text_input("Model", cfg.detection.model, key="cfg_det_model")
    cfg.detection.imgsz = st.number_input("Image size", 320, 1280, int(cfg.detection.imgsz), 64, key="cfg_det_imgsz")
    cfg.detection.conf = st.slider("Confidence", 0.05, 0.95, float(cfg.detection.conf), 0.05, key="cfg_det_conf")
    cfg.detection.iou = st.slider("IoU", 0.1, 0.9, float(cfg.detection.iou), 0.05, key="cfg_det_iou")
    cfg.detection.tracker = st.text_input("Tracker", cfg.detection.tracker, key="cfg_det_tracker")
    cfg.detection.frame_stride = st.number_input("Frame stride", 1, 10, int(cfg.detection.frame_stride), key="cfg_det_stride")
    cls = st.text_input("Class whitelist (indices, comma; blank = all)", ",".join(str(c) for c in (cfg.detection.classes or [])), key="cfg_det_classes")
    cfg.detection.classes = [int(x) for x in _parse_list(cls) if x.isdigit()]


def _render_events(cfg) -> None:
    st.markdown("**Events & clips**")
    cfg.events.trigger_classes = _parse_list(st.text_input("Trigger classes (comma)", ", ".join(cfg.events.trigger_classes)))
    cfg.events.min_presence_sec = st.number_input("Min presence (s)", 0.0, 60.0, float(cfg.events.min_presence_sec), 0.5)
    cfg.events.cooldown_sec = st.number_input("Cooldown (s)", 0.0, 3600.0, float(cfg.events.cooldown_sec), 1.0)
    cfg.events.clip_pre_sec = st.number_input("Clip pre-roll (s)", 0.0, 30.0, float(cfg.events.clip_pre_sec), 0.5)
    cfg.events.clip_post_sec = st.number_input("Clip post-roll (s)", 0.0, 60.0, float(cfg.events.clip_post_sec), 0.5)
    cfg.events.clip_fps = st.number_input("Clip FPS", 2.0, 30.0, float(cfg.events.clip_fps), 1.0)
    cfg.events.clip_max_width = st.number_input("Clip max width", 320, 1920, int(cfg.events.clip_max_width), 64)
    st.markdown("**Fall detection**")
    cfg.events.fall_bbox_ratio = st.number_input("Fall bbox ratio", 0.5, 2.0, float(cfg.events.fall_bbox_ratio), 0.05)
    cfg.events.fall_min_sec = st.number_input("Fall sustain (s)", 0.5, 30.0, float(cfg.events.fall_min_sec), 0.5)
    cfg.events.fall_angle_deg = st.number_input("Fall torso angle (deg)", 20.0, 90.0, float(cfg.events.fall_angle_deg), 1.0)
    st.markdown("**Abandoned object**")
    cfg.events.abandoned_sec = st.number_input("Abandoned (s)", 5.0, 600.0, float(cfg.events.abandoned_sec), 1.0)
    cfg.events.abandoned_owner_radius_px = st.number_input("Owner radius (px)", 50.0, 1000.0, float(cfg.events.abandoned_owner_radius_px), 10.0)
    cfg.events.abandoned_classes = _parse_list(st.text_input("Abandoned classes (comma)", ", ".join(cfg.events.abandoned_classes)))


def _render_ai(cfg) -> None:
    st.markdown("### 🤖 AI summaries (VLM)")
    cfg.vlm.enabled = st.checkbox("Enable", value=cfg.vlm.enabled, key="cfg_vlm_en")
    cfg.vlm.provider = st.selectbox("Provider", ["openai", "ollama"], index=0 if cfg.vlm.provider == "openai" else 1, key="cfg_vlm_provider")
    cfg.vlm.base_url = st.text_input("Base URL", cfg.vlm.base_url, key="cfg_vlm_base")
    cfg.vlm.api_key = st.text_input("API key", cfg.vlm.api_key, type="password", key="cfg_vlm_key")
    cfg.vlm.model = st.text_input("Model", cfg.vlm.model, key="cfg_vlm_model")
    cfg.vlm.max_keyframes = st.number_input("Max keyframes", 1, 6, int(cfg.vlm.max_keyframes), key="cfg_vlm_kf")
    cfg.vlm.timeout_sec = st.number_input("Timeout (s)", 10, 300, int(cfg.vlm.timeout_sec), key="cfg_vlm_timeout")

    st.markdown("### 🚗 Vehicle plates (ANPR)")
    cfg.alpr.enabled = st.checkbox("Enable", value=cfg.alpr.enabled, key="cfg_alpr_en")
    cfg.alpr.zones_only = st.checkbox("Only in parking zones", value=cfg.alpr.zones_only, key="cfg_alpr_zones")
    cfg.alpr.min_conf = st.slider("OCR confidence", 0.0, 0.9, float(cfg.alpr.min_conf), 0.05, key="cfg_alpr_conf")
    cfg.alpr.throttle_sec = st.number_input("Throttle (s)", 1.0, 60.0, float(cfg.alpr.throttle_sec), 1.0, key="cfg_alpr_throttle")
    cfg.alpr.languages = st.text_input("Languages (comma)", cfg.alpr.languages, key="cfg_alpr_langs")
    cfg.alpr.plate_model = st.text_input("Plate model path (optional)", cfg.alpr.plate_model, key="cfg_alpr_pm")
    cfg.alpr.save_crop = st.checkbox("Save plate crops", value=cfg.alpr.save_crop, key="cfg_alpr_save")

    st.markdown("### 👤 Face recognition")
    cfg.face.enabled = st.checkbox("Enable", value=cfg.face.enabled, key="cfg_face_en")
    cfg.face.model_name = st.text_input("Model", cfg.face.model_name, key="cfg_face_model")
    cfg.face.detector_backend = st.text_input("Detector backend", cfg.face.detector_backend, key="cfg_face_backend")
    cfg.face.min_conf = st.slider("Match threshold", 0.2, 0.9, float(cfg.face.min_conf), 0.05, key="cfg_face_conf")
    cfg.face.throttle_sec = st.number_input("Throttle (s)", 1.0, 60.0, float(cfg.face.throttle_sec), 1.0, key="cfg_face_throttle")
    cfg.face.save_crop = st.checkbox("Save face crops", value=cfg.face.save_crop, key="cfg_face_save")

    st.markdown("### 👥 ReID (cross-camera tracking)")
    cfg.reid.enabled = st.checkbox("Enable", value=cfg.reid.enabled, key="cfg_reid_en")
    cfg.reid.model_name = st.text_input("Model", cfg.reid.model_name, key="cfg_reid_model")
    cfg.reid.min_conf = st.slider("Similarity threshold", 0.3, 0.9, float(cfg.reid.min_conf), 0.05, key="cfg_reid_conf")
    cfg.reid.throttle_sec = st.number_input("Throttle (s)", 1.0, 60.0, float(cfg.reid.throttle_sec), 1.0, key="cfg_reid_throttle")
    cfg.reid.save_crop = st.checkbox("Save appearance crops", value=cfg.reid.save_crop, key="cfg_reid_save")


def _render_security(cfg) -> None:
    st.markdown("### 🔒 Privacy")
    cfg.privacy.blur_enabled = st.checkbox("Blur faces/bodies", value=cfg.privacy.blur_enabled)
    cfg.privacy.blur_mode = st.selectbox("Blur mode", ["face", "body"], index=0 if cfg.privacy.blur_mode == "face" else 1)

    st.markdown("### 🗑️ Retention")
    cfg.retention.retention_days = st.number_input("Retention (days, 0 = forever)", 0, 3650, int(cfg.retention.retention_days))
    cfg.retention.purge_interval_sec = st.number_input("Purge interval (s)", 0, 86400, int(cfg.retention.purge_interval_sec))

    st.markdown("### 🔐 Login & roles")
    cfg.auth.enabled = st.checkbox("Enable login", value=cfg.auth.enabled)
    if cfg.auth.enabled:
        for u in list(cfg.auth.users):
            c1, c2 = st.columns([5, 1])
            c1.markdown("**" + u.username + "** · " + u.role)
            if c2.button("Remove", key="rmuser_" + u.username):
                cfg.auth.users.remove(u)
                st.rerun()
        n = st.text_input("Username", key="new_user")
        pw = st.text_input("Password", type="password", key="new_pw")
        r = st.selectbox("Role", ["admin", "security", "manager", "viewer"], key="new_role")
        if st.button("Add user") and n and pw:
            from smartcam.config import AuthUser

            cfg.auth.users.append(AuthUser(username=n, password_hash=hash_password(pw), role=r))
            st.rerun()

    st.markdown("### 🔗 Webhook")
    cfg.webhook.enabled = st.checkbox("Enable", value=cfg.webhook.enabled, key="wh_en")
    cfg.webhook.url = st.text_input("URL", cfg.webhook.url, key="cfg_wh_url")
    cfg.webhook.timeout_sec = st.number_input("Timeout (s)", 1.0, 120.0, float(cfg.webhook.timeout_sec), key="cfg_wh_timeout")

    st.markdown("### 📊 Reports")
    cfg.report.enabled = st.checkbox("Enable reports", value=cfg.report.enabled)
    cfg.report.interval = st.selectbox("Interval", ["daily", "weekly"], index=0 if cfg.report.interval == "daily" else 1)
    cfg.report.notify = st.checkbox("Send report via notifications", value=cfg.report.notify)

    st.markdown("### 🔔 Notifications")
    cfg.notify.enabled = st.checkbox("Enable", value=cfg.notify.enabled, key="notify_en")
    cfg.notify.apprise_url = st.text_input("Apprise URL", cfg.notify.apprise_url, help="e.g. ntfy://topic, pushover://user:token, tgram://botToken/chatId")
    cfg.notify.e2e_encrypt = st.checkbox("ntfy E2E (experimental)", value=cfg.notify.e2e_encrypt)
    cfg.notify.ntfy_topic = st.text_input("ntfy topic", cfg.notify.ntfy_topic)
    cfg.notify.ntfy_public_key = st.text_input("ntfy public key", cfg.notify.ntfy_public_key)
    cfg.notify.ntfy_server = st.text_input("ntfy server", cfg.notify.ntfy_server)


# --------------------------------------------------------------------------- #
# About
# --------------------------------------------------------------------------- #
def render_about() -> None:
    st.subheader("About SmartCam")
    st.markdown(
        """
SmartCam turns any RTSP camera, webcam, or video file into an intelligent
surveillance system powered by **YOLOv8** object detection and multi-object
tracking (ByteTrack).

**Features**
- Real-time object detection + tracking
- Automatic event clips (with pre-roll) and thumbnails
- Smart search (objects, time-of-day, dates, free text)
- AI event summaries via a pluggable vision-language model
- Mobile notifications (ntfy, Pushover, Telegram, ... via apprise)
- Hotel safety: loitering, restricted-zone intrusion, queue/crowd alerts,
  fall detection, abandoned-object detection
- Parking occupancy counting + foot-traffic heatmaps
- Privacy face/body blurring, data retention, dashboard login + roles
- Webhook/API event delivery, audit logging, dark theme

**Quick start**
1. (optional) fetch a demo clip:
   .venv/Scripts/python scripts/download_demo.py
2. run the dashboard:
   .venv/Scripts/python -m streamlit run app.py

**HTTPS** (recommended for production)
   .venv/Scripts/python -m streamlit run app.py \
     --server.sslCertFile path/to/cert.pem \
     --server.sslKeyFile path/to/key.pem

**Headless mode**
   .venv/Scripts/python scripts/run_pipeline.py --config config.json
"""
    )
    st.caption("Working directory: " + str(ROOT))


ROLE_TABS = {
    "admin": ["live", "alerts", "events", "import", "search", "analytics", "plates", "faces", "reid", "settings", "about"],
    "security": ["live", "alerts", "events", "import", "search", "analytics", "plates", "faces", "reid", "about"],
    "manager": ["live", "alerts", "events", "search", "analytics", "plates", "about"],
    "viewer": ["live", "events", "search", "about"],
}


def _build_tabs(mgr, source_id, role):
    all_tabs = [
        ("live", "📺 Live", lambda: render_live(mgr, source_id)),
        ("alerts", "🚨 Alerts", lambda: render_alerts(mgr)),
        ("events", "🎞️ Events", lambda: render_events(mgr)),
        ("import", "📤 Import", lambda: render_import(mgr)),
        ("search", "🔎 Smart search", lambda: render_search(mgr)),
        ("analytics", "📊 Analytics", lambda: render_analytics(mgr, source_id)),
        ("plates", "🚗 Plates", lambda: render_plates(mgr)),
        ("faces", "👤 Faces", lambda: render_faces(mgr)),
        ("reid", "👥 Track person", lambda: render_reid(mgr)),
        ("settings", "⚙️ Settings", lambda: render_settings(mgr)),
        ("about", "ℹ️ About", lambda: render_about()),
    ]
    allowed = ROLE_TABS.get(role, ROLE_TABS["viewer"])
    return [(label, fn) for (key, label, fn) in all_tabs if key in allowed]


def main() -> None:
    cfg = load_config()
    remote = bool(os.environ.get("SMART_CAM_API_URL", ""))
    if (cfg.auth.enabled or remote) and not st.session_state.get("role"):
        render_login(cfg)
        st.stop()
    if st.session_state.get("login_ts") and time.time() - st.session_state["login_ts"] > SESSION_TIMEOUT_SEC:
        _audit("session_timeout")
        st.session_state.clear()
        st.rerun()
    role = st.session_state.get("role", "admin")

    mgr = get_manager()
    if remote and st.session_state.get("api_token") and getattr(mgr, "_token", None) != st.session_state["api_token"]:
        mgr.set_token(st.session_state["api_token"])
        mgr._reload()
    source_id = render_sidebar(mgr, role)
    alert_watch(mgr)
    visible = _build_tabs(mgr, source_id, role)
    tabs = st.tabs([label for label, _ in visible])
    for tab, (_, fn) in zip(tabs, visible):
        with tab:
            fn()


if __name__ == "__main__":
    main()

