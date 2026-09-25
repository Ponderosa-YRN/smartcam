# SmartCam — Demo Smoke-Test Checklist

Run in order the morning of the presentation. About 15 minutes, and you will have
personally verified every screen the client will see. The client-facing talking
points live in docs/PRESENTATION_SCRIPT.md — this is the "what to click and what
must be true" companion.

## 0. Pre-flight (verified as of the last build — no action needed)

- [x] Python 3.11 venv at .venv with torch (CPU), ultralytics, OpenCV, FastAPI, aiortc.
- [x] Model yolov8n.onnx present (the default, ~35% faster than the .pt).
- [x] Database migrated to schema v12 (verified on a copy: 1 admin, 1 tenant, 33 events).
- [x] Automated test suite: 39 passed.
- [x] API exposes 77 routes (REST + WebSocket + MJPEG + WebRTC).

## 1. Start the backend — Terminal 1, from the repo ROOT

    cd "C:\Users\Agtrdr\Desktop\Smart cam"
    .venv\Scripts\python.exe run_api.py

- [ ] Open http://localhost:8000/api/health → {"status":"ok","service":"smartcam"}
- [ ] Open http://localhost:8000/docs → the auto-generated API docs load (impressive for technical buyers).
- [ ] Terminal shows "SmartCam API started with N source(s)" and no tracebacks.
  - Red "NativeCommandError" lines in PowerShell are cosmetic (stderr echoed red), not real errors.

## 2. Start the frontend — Terminal 2

    cd frontend
    npm run dev

- [ ] Open http://localhost:3000 → redirected to the login page.
- [ ] Log in with your admin credentials.

> If login says "failed to fetch", the API isn't running (step 1) or isn't on
> port 8000. If it says 401, the username/password is wrong.

## 3. Core demo flow (the money screens)

### 3.1 Live view — http://localhost:3000/live
- [ ] Cameras appear in the grid; video streams with tracking boxes + labels.
- [ ] Toggle MJPEG ↔ WebRTC (top of the page). WebRTC should be noticeably snappier.

### 3.2 Import a video (if no live camera)
- [ ] Import page → upload a sample clip → source is created and starts processing.
- [ ] Toggle Fast processing off for a visual demo (shows boxes); on for speed.

### 3.3 Events + clips
- [ ] Events page lists detections (person/car/…).
- [ ] Open an event → clip plays and thumbnail shows.
- [ ] If VLM is configured (OpenAI key set), the event shows an AI summary sentence.

### 3.4 Alert center
- [ ] Alerts page shows open alerts.
- [ ] Acknowledge / Resolve / Escalate all work and move the row state.

### 3.5 Smart search
- [ ] Search page → type "person in lobby" or "red car" → returns matching events.

### 3.6 Analytics
- [ ] Analytics page shows occupancy over time and the heatmap for a source.

### 3.7 Admin (the SaaS story — this is the differentiator)
- [ ] Admin → Tenants: add a tenant, see the list.
- [ ] Admin → Billing & usage: pick a tenant → cameras/events/storage metered; change plan (free/pro/enterprise).
- [ ] Admin → Edge devices: pick a tenant → Provision device → copy the token once → Rotate token / Delete.
- [ ] Admin → Invite users: send an invite → open the link in an incognito window → register into the tenant.

## 4. Optional — Streamlit dashboard (Terminal 3)

    cd "C:\Users\Agtrdr\Desktop\Smart cam"
    .venv\Scripts\python.exe -m streamlit run app.py

- [ ] http://localhost:8501 shows the same pipeline through the quick dashboard.

## 5. Optional — Edge + cloud split (the architecture headline)

On a second machine (or a second terminal pointed at a different camera):

    .venv\Scripts\python.exe edge_agent.py --api-url http://<cloud-host>:8000 --token scd_<tenant>.<signed>

- [ ] Events + occupancy from the edge box appear in the cloud tenant's Events/Analytics.
- [ ] Admin → Edge devices shows the device's last_seen updating (heartbeat).

## 6. Troubleshooting quick reference

| Symptom | Fix |
| --- | --- |
| Frontend "failed to fetch" on login | API not running / wrong port. Run step 1 from repo ROOT (not frontend). |
| 401 on login | Wrong username/password. |
| Live view empty | No sources enabled — import a video or add a camera in Settings/Import. |
| WebRTC tile says "unavailable" | Server missing aiortc, or remote camera behind symmetric NAT (needs TURN — see config webrtc). |
| API won't start | Run from repo ROOT; check port 8000 isn't already in use. |
| "no module named X" | Missing dep — re-run the venv installs, or ask me. |

## 7. Honest capability notes (say these if asked)

- Detection/tracking runs on CPU here; on a GPU box the same config runs faster via detection.device.
- ANPR / face recognition / ReID / VLM summaries need their optional deps/keys (easyocr, deepface, torchreid, an OpenAI-compatible key) — they degrade gracefully, not crash.
- Billing is metering + plan limits; live Stripe charges are a follow-up.
