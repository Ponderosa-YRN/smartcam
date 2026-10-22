# Technical Requirements Document — SmartCam
**Version 2.0 · reflects commit `f6b27ea`**

---

## 1. System shape

```
Browser → Caddy (TLS, HTTP/3, one origin)
              ├── /smartapi/*, /auth/*, /ws/* → FastAPI 127.0.0.1:8000
              └── everything else            → Next.js 127.0.0.1:3000

FastAPI → PipelineManager (thread per source) → YOLOv8 + ByteTrack
        → EventStore (SQLAlchemy Core) → SQLite or PostgreSQL
        → clip/thumb storage (local or S3) → optional VLM summaries
        → optional aiortc WebRTC

Edge box (optional) → edge_agent.py → POST /api/ingest/{events,occupancy,media}
```

| Component | Path | Responsibility |
|---|---|---|
| API | `smartcam/api.py` | 78 routes, auth middleware, tenant enforcement |
| Pipeline | `smartcam/pipeline.py` | Detection, tracking, zones, falls, event assembly |
| Store | `smartcam/db.py` | Thread-safe SQLAlchemy Core, 15 tables, migrations |
| Config | `smartcam/config.py` | Dataclass sections, JSON load/save |
| Auth | `smartcam/auth.py`, `security.py` | scrypt hashes, HMAC tokens |
| Reports | `smartcam/report_pdf.py` | One-page incident PDF via Pillow |
| Notify | `smartcam/notify.py` | Apprise, one URL per line |
| Pose | `smartcam/pose.py` | Torso angle for possible-fall |
| Web app | `frontend/` | Next.js 15 / React 19 / TypeScript — the only UI |
| Co-pilot | `frontend/lib/copilot.ts` | Provider-agnostic agent loop, 7 tools |

**Removed:** the Streamlit dashboard (`app.py`, 945 lines) and the `streamlit` dependency. It had a
role login but **no tenant concept** — it read the shared database directly.

---

## 2. Authentication and authorisation

| Principal | Credential | Lifetime |
|---|---|---|
| User | HMAC bearer token | 12 h |
| User | Refresh token | 30 d |
| Device | Device token + generation counter | long-lived, rotatable |

**Requirements**

- **R1** Every route requires auth except `/api/health`, `/auth/login`, `/auth/refresh`, `/auth/register`, docs, `/invites/*`
- **R2** scrypt password hashing; never logged
- **R3** Ladder is admin > manager > security > viewer; `device` is a token principal. Camera control and config: admin/manager. Triage additionally admits `security`. Reads: any authenticated principal in the tenant
- **R4** Tenant comes from the token, never the path or body
- **R5** Any route carrying an id verifies ownership; wrong tenant returns **404**, not 403, so the API never confirms another tenant's record exists
- **R6** Role and tenant are re-read from the database per request, so revocation is immediate
- **R7** Login throttled at 8 failures per `host|username` per 5 minutes
- **R8** Registration is closed unless `SMART_CAM_ALLOW_SIGNUP` is set
- **R9** Plan changes require `SMART_CAM_PLATFORM_KEY`
- **R10** Enabling face recognition or re-ID requires `privacy.biometrics_consent`

---

## 3. Interfaces

**HTTP** — JSON in/out; errors as `{"detail": ...}`; 401 unauthenticated, 403 wrong role, 404 missing **or not yours**.

**WebSocket** — `/ws/events` (tenant-filtered event push) and `/ws/webrtc/{source_id}` (SDP/ICE, source-ownership checked). Both accept the token as a **bearer subprotocol** and still accept `?token=` for older clients.

**Device ingest** — `/api/ingest/events` (≤500), `/api/ingest/occupancy` (≤2000), `/api/ingest/media/{event_id}`. Device-authenticated, stamped with the device's tenant.

**Uploads** — ≤2 GiB, extension whitelisted, streamed with a running byte counter; the partial file is deleted on overflow.

**Reports** — `GET /api/events/{id}/report` returns `application/pdf`, tenant-checked, generation audited.

---

## 4. Configuration

JSON with typed sections: sources, detection, events, zones, privacy, retention, storage, auth,
webhook, report, alpr, face, reid, vlm, notify, webrtc, app. Unknown keys are ignored on load, so
removing a field cannot break an existing file.

| Env | Purpose |
|---|---|
| `SMART_CAM_CONFIG` | Config path (must be on the volume) |
| `SMART_CAM_TOKEN_SECRET` | HMAC signing key |
| `SMART_CAM_CORS_ORIGINS` | Allowed origins. **Empty by default** — production is same-origin |
| `SMART_CAM_ALLOW_SIGNUP` | Opens public registration. Closed unless set |
| `SMART_CAM_PLATFORM_KEY` | Required for plan changes |
| `SMART_CAM_MAX_STREAMS` | MJPEG viewer cap (default 20) |
| `SMART_CAM_CLOUD_ONLY` | Control-plane only. **Dropped by the deploy script** — the deployment runs the full pipeline |
| `COPILOT_API_KEY/BASE_URL/MODEL` | Co-pilot provider |

**Secrets never enter an image layer**: `.dockerignore` excludes `config.json`, `.env*`, `.security-audit`.

---

## 5. Deployment

| Item | Value |
|---|---|
| Domain | `https://agay.tech` |
| Routing | `/smartapi/*` → API, else Next.js |
| Image | **Root `Dockerfile`** — torch CPU, OpenCV, ultralytics, aiortc |
| Bindings | API `127.0.0.1:8000` + `[::1]:8000`; web `127.0.0.1:3000` |

**Deploy requirements**

- **D1** Refuse to recreate a container whose `/app/data` is not a volume
- **D2** Carry `config.json` across a rebuild; roll back on failure
- **D3** Health-check on loopback so it works while the site is firewalled
- **D4** Re-runnable after an interruption (clear a stale rollback container)
- **D5** Strip `SMART_CAM_CLOUD_ONLY` from inherited env, or a rebuild silently keeps the blind control plane
- **D6** Scripts recorded `100755` so a manual `chmod` can't block the next pull
- **D7** Firewall rules persisted via `netfilter-persistent`

---

## 6. Performance

| Metric | Target | Basis |
|---|---|---|
| Detection | ≥5 fps/source on CPU | yolov8n at 640 px |
| Event latency | ≤5 s | 1 s WebSocket poll + pipeline |
| API p95 | <300 ms list endpoints | Indexed queries |
| Concurrent WebRTC | ~5 per source | one relay per peer |
| Cameras per VPS | 25 (Pro limit) | **Unmeasured**, CPU-bound |

---

## 7. Observability

Logging via `logging`; `audit.log` records registrations, logins, account changes, biometric consent
and report generation; `docker logs` is the only aggregation.

**Present:** hourly disk check → Telegram; 5-minute site check that requires the page to *render* →
Telegram.
**Absent:** anything outside the box. Nothing can report the box being unreachable, and no metrics.

---

## 8. Compliance requirements (NDPA / GAID)

| Requirement | Status |
|---|---|
| Recorded lawful basis for biometrics | Met — consent gate, audited |
| Retention limit | Met — 30-day default |
| Access limitation and roles | Met |
| Audit of personal-data access | Partial |
| **DPIA with NDPC** | Not met |
| **Signage** | Not met |
| **Data subject requests** | Not met |
| **Nigerian residency** | Not met |

---

## 9. Technical debt

1. **AGPL-3.0** on `ultralytics` — commercial SaaS obligation
2. WebSocket routes untested (both handlers loop forever)
3. No route-level auth test for the WebSocket paths
4. Tenant stamping still uses `local_tenant_id` on some legacy write paths
5. No index review since tenant-first reads became the norm
6. Schema version numbering has gaps (8–10 absent)
7. Legacy non-test scripts in `tests/`
