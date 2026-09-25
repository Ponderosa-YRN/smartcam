# SmartCam — Product & Technical Overview
## A complete bring-you-up-to-speed brief (client-presentation ready)

---

## 1. What it is (the pitch)

SmartCam turns **ordinary CCTV cameras** (RTSP, webcams, or video files) into an
**AI-powered intelligent surveillance platform**. It watches the video in real
time, understands what is happening (people, cars, queues, falls, plates, faces),
raises alerts, records short clips, and lets staff search the footage by what
happened — not by timestamp.

**One line for the client:** "Your existing cameras, upgraded with AI eyes —
detection, tracking, instant alerts, and searchable video."

**Target market:** hotels and multi-site hospitality/security operations.

---

## 2. Architecture

Two ways the system runs today:

1. **Local (single box):** the Streamlit dashboard runs the whole pipeline
   in-process. Good for a demo or a single site.
2. **Split (production):** a FastAPI backend runs the detection pipeline
   headlessly and exposes a REST + WebSocket API; a React/Next.js web app talks
   to it. This is the product architecture.

    Cameras (RTSP/webcam/file)
              |
              v
    [ Detection pipeline ]  -- YOLOv8 + ByteTrack, zones, events, clips
              |
              v
    [ FastAPI backend ]     -- auth, REST API, WebSocket, file storage
              |                        |
              v                        v
    [ Next.js web app ]     [ Streamlit dashboard (admin/local) ]
              |
              v
    [ SQLite database ]  (events, plates, faces, users, tenants, ...)

**Future (documented in docs/ARCHITECTURE.md):** hybrid **edge + cloud** —
one on-site box per hotel does the heavy inference near the cameras; a cloud
control plane handles identity, tenants, notifications, and cross-site search.

---

## 3. Backend (Python)

The backend is a Python package in the **smartcam/** folder (24 modules).

### 3.1 The pipeline (smartcam/pipeline.py)
- **CameraPipeline** runs the per-camera loop: read frame -> motion check ->
  detect + track -> run safety rules -> record clips -> draw boxes.
- **PipelineManager** supervises many cameras, runs a watchdog (auto-restart),
  camera health checks, escalation timer, occupancy sampling, and reports.
- **Adaptive speed:** it lowers resolution and skips frames when a scene is idle,
  and only runs full detection when there is motion — a big CPU saver.

### 3.2 Detection & tracking (smartcam/detector.py)
- **YOLOv8n** (the "nano" model, 3.2M parameters) for object detection.
- **ByteTrack** for multi-object tracking (gives each person/car a stable ID).
- Ships with **ONNX Runtime** by default (~35% faster than PyTorch on CPU).
- Detects COCO classes: person, car, truck, bus, motorcycle, bicycle, bags, etc.

### 3.3 Event intelligence (the hotel-safety features)
The pipeline turns detections into seven **event types**:

| Event | What triggers it |
|---|---|
| detection | a tracked object of interest appears |
| loitering | a person stays in a zone too long |
| intrusion | someone enters a restricted zone (or outside allowed hours) |
| queue | too many people in a zone (crowd) |
| fall | a person falls (pose-based torso angle) |
| abandoned | a bag/suitcase left with no owner nearby |
| parking | vehicles counted against a parking zone's capacity |

Each event records a **clip** (with pre-roll), a **thumbnail**, and metadata.

### 3.4 Recognition features
- **ANPR / plate reading** (smartcam/alpr.py) — reads license plates via EasyOCR,
  English and Nigeria plate patterns.
- **Face recognition** (smartcam/face.py) — deepface/Facenet, with a **consent**
  flag and one-click "delete this person" for privacy compliance.
- **Cross-camera person tracking / ReID** (smartcam/reid.py) — torchreid OSNet
  re-identifies the same person across different cameras.

### 3.5 AI summaries (smartcam/summarize.py)
A pluggable **Vision-Language Model** writes a natural-language summary of each
event clip ("A person entered through the side door and walked to the lobby..."),
via OpenAI-compatible APIs or a local Ollama model.

### 3.6 Notifications & integrations
- **Notifications** (smartcam/notify.py) — push alerts via Apprise/ntfy,
  Pushover, Telegram, etc., with optional **end-to-end encryption**.
- **Webhooks** (smartcam/webhook.py) — POST event JSON to any URL.
- **Reports** (smartcam/analytics.py) — daily/weekly incident reports,
  foot-traffic heatmaps, and occupancy charts.

### 3.7 Data & storage (smartcam/db.py)
A single SQLite database (schema v8) with **12 tables**:
events, plates, faces, face_matches, appearances, identities, sightings,
occupancy_samples, users, tenants, sites, devices. Automatic migrations and
a **data retention / auto-purge** policy.

### 3.8 Privacy (a strong selling point)
- Face/body **blurring** in live view and recorded clips.
- **Consent** flags on face data + GDPR-style "delete a person".
- **Retention** auto-deletion.
- **E2E-encrypted** notifications.

### 3.9 Auth & security
- **Password hashing** with scrypt (strong KDF).
- **Bearer tokens** (HMAC-signed, expiring: 12h access / 30d refresh).
- **Roles (RBAC):** admin, security, manager, viewer — enforced on every request.
- **Multi-tenancy:** every row is scoped to a tenant; users only see their
  own tenant's data.

### 3.10 Multi-tenancy (for the SaaS pitch)
- **tenants** -> **sites** -> **devices** hierarchy.
- Each tenant gets isolated users, cameras, and data.
- Admin can create/manage tenants, sites, and edge devices.

### 3.11 The API (smartcam/api.py + run_api.py)
A FastAPI backend with **~50 endpoints** + a live WebSocket:

- **Auth:** /auth/login, /auth/refresh, /auth/logout, /auth/me, /auth/users
- **Cameras:** /api/sources, /api/start, /api/stop, /api/status, /api/frame, /api/stream
- **Events:** /api/events, /api/open_alerts, /api/ack, /api/resolve, /api/assign, /api/escalate
- **Media:** /api/clips, /api/thumbs, /api/upload
- **AI data:** /api/plates, /api/faces, /api/face_matches, /api/identities, /api/sightings
- **Analytics:** /api/search, /api/occupancy, /api/occupancy_history, /api/heatmap, /api/count
- **Config:** /api/config
- **Tenants:** /tenants and sub-resources
- **Live feed:** /ws/events (WebSocket push)

---

## 4. Frontend (Next.js — frontend/ folder)

A React 19 + Next.js 15 (App Router, TypeScript) web app. Pages:

| Page | What it shows |
|---|---|
| Login | sign-in (stores a bearer token) |
| Dashboard | live event feed + recent events |
| Live | multi-camera grid with live annotated frames |
| Alerts | open alerts with Acknowledge / Resolve + clip playback |
| Events | full event history with filters + clip playback |
| Import | upload a video and watch it be analyzed live |
| Search | natural-language search ("person at night") |
| Analytics | occupancy metrics + 24h history |
| Plates | license-plate reads |
| Faces | registered faces + recent matches |
| Track | cross-camera person sightings |
| Settings | full config editor (JSON) |
| Admin | tenants + user management |

The nav is role-aware (admin/manager see Import, Settings, Admin).

---

## 5. The Streamlit dashboard (app.py)

A second UI (Streamlit) that runs the pipeline **in-process** — used for local
admin/ops and as the original rapid prototype. It has the same tabs (Live,
Alerts, Events, Import, Search, Analytics, Plates, Faces, Track, Settings).

---

## 6. Performance

The system is built to run well **without a GPU**:

- **ONNX Runtime** (default) — ~35% faster than PyTorch on CPU.
- **Motion gating** — skips detection when the scene is still.
- **Adaptive resolution/stride** — drops to low res when idle.
- **Fast assessment mode** — imgsz 320 + frame skipping for quick video analysis.
- **Next step:** OpenVINO on Intel CPUs (another ~2-3x free speedup), or a GPU
  (a single T4/L4 is far more than enough for many cameras).

---

## 7. How to run / demo

Two terminals:

    # Terminal 1 — API (repo root)
    .venv\Scripts\python run_api.py

    # Terminal 2 — frontend (frontend/ folder)
    npm run dev

Open http://localhost:3000 and sign in as admin.

**Suggested live demo flow:**
1. Show **Live** (cameras with live detection boxes).
2. Import a short video in **Import** and let the audience watch the AI track
   people/cars and draw boxes in real time.
3. Show the **Events/Alerts** list, play a recorded **clip**, and show an
   **AI-written summary**.
4. Demo **Search**: "person at night" or "car yesterday".
5. Show **Analytics** (occupancy + heatmap) and **Plates/Faces/Track** if time.
6. End with the **Admin** page: roles, tenants, users — the multi-site story.

---

## 8. Talking points for the client

1. **Uses your existing cameras** — no new hardware required.
2. **Real-time AI** — detects, tracks, and understands what's happening.
3. **Proactive safety** — loitering, intrusion, crowd, fall, abandoned baggage.
4. **Instant alerts** to phones (with end-to-end encryption).
5. **Searchable video** — find "person in a red shirt near the pool" instead of
   scrubbing hours of footage.
6. **Vehicle intelligence** — automatic plate reading and parking counts.
7. **People intelligence** — face recognition and cross-camera tracking.
8. **Privacy-first** — blurring, consent, retention, encrypted notifications.
9. **Multi-site, multi-tenant** — one dashboard for all your properties.
10. **Runs on affordable hardware** — optimized for CPU, GPU optional.

---

## 9. Roadmap (what's next)

- **P1 (in progress):** complete the web app pages + clip playback.
- **P2 (in progress):** multi-tenancy (tenant data model done; onboarding,
  invites, object storage, billing next).
- **P3:** edge + cloud split (on-site box per hotel + cloud control plane).
- **P4:** scale & ops — OpenVINO/GPU, WebRTC streaming, monitoring, compliance.
