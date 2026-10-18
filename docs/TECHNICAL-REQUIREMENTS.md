# Technical Requirements Document — SmartCam

**Status:** Draft 1 · **Date:** 2026-10-17
**Companion documents:** `docs/PRD.md`, `docs/BACKEND-SCHEMA.md`, `docs/IMPLEMENTATION-PLAN.md`

---

## 1. Purpose and scope

Defines the technical shape of the system as built: components, interfaces, deployment,
configuration, and the requirements that are not optional (security, performance, operability).
It describes the committed source, not an aspiration.

## 2. System context

Three tiers plus an optional edge tier:

```
   Browser (dashboard, marketing site)
        │  HTTPS + WSS
        ▼
   Caddy  ── TLS, HTTP/3, single origin ──►  https://agay.tech
        │
        ├── /smartapi/*, /auth/*, /ws/*  ──►  FastAPI (uvicorn)   127.0.0.1:8000
        └── everything else             ──►  Next.js 15          127.0.0.1:3000

   FastAPI ──► PipelineManager ──► YOLOv8 + ByteTrack ──► RTSP / USB / file sources
            ──► EventStore (SQLAlchemy Core) ──► SQLite (default) or PostgreSQL
            ──► Clip + thumbnail storage (local or S3)
            ──► Optional VLM provider (event summaries)
            ──► Optional TURN server (WebRTC over NAT)

   Edge agent (on-site, optional) ──► POST /api/ingest/{events,occupancy,media}
```

## 3. Components

| Component | Path | Responsibility |
|---|---|---|
| API / control plane | `smartcam/api.py` | 77 routes; auth middleware; tenant enforcement |
| Pipeline manager | `smartcam/pipeline.py` | One worker per source; detection, tracking, event assembly |
| Event store | `smartcam/db.py` | Thread-safe SQLAlchemy Core wrapper; migrations |
| Config | `smartcam/config.py` | Dataclass sections; load/save to JSON |
| Auth primitives | `smartcam/auth.py`, `smartcam/security.py` | scrypt hashing, HMAC tokens |
| Device tokens | `smartcam/secrets.py` | Device identity + generation counter |
| Billing stub | `smartcam/billing.py` | Plan limits, usage metering |
| WebRTC | `smartcam/webrtc.py` | aiortc peer connections |
| Shared UI | `app.py` | Legacy Streamlit dashboard (superseded by Next.js) |
| Edge agent | `edge_agent.py` | On-site capture and upstream push |
| Web app | `frontend/` | Next.js 15, React 19, TypeScript |
| Co-pilot | `frontend/lib/copilot.ts`, `frontend/app/copilot/route.ts` | Provider-agnostic agent loop |

## 4. Technology choices and rationale

| Choice | Rationale | Cost accepted |
|---|---|---|
| FastAPI + uvicorn | Async, typed, OpenAPI for free | Single process; in-memory state (throttle) does not scale out |
| SQLAlchemy Core | One code path for SQLite and Postgres | No ORM conveniences |
| SQLite default | Zero-ops for a single-VPS product | Write lock; needs Postgres beyond one API instance |
| Next.js 15 App Router | SSR for the marketing site, client components for the app | Two build artifacts to ship |
| YOLOv8 + ByteTrack | Best accuracy per CPU-hour at this scale | Model weights are large; first run downloads |
| aiortc | Native WebRTC without a media server | Fragile across NAT; TURN may be required |
| itsdangerous HMAC tokens | Simple, stateless, no session store | Revocation requires a per-request DB re-read (now implemented) |
| Caddy | Automatic TLS, HTTP/3, one origin (no CORS in production) | Another process to operate |
| Docker Compose | Reproducible, one-command deploy | No orchestration; single point of failure |

## 5. Authentication and authorization requirements

**Principal types**

| Type | Credential | Lifetime | Scope |
|---|---|---|---|
| User | Bearer access token (HMAC) | 12 h | Role + tenant |
| User | Refresh token | 30 d | Mints new access tokens |
| Device | Device token with generation counter | Long-lived, rotatable | One device, one tenant |

**Requirements**

- R1 · Every non-public route requires authentication. Public set is explicit and minimal:
  `/api/health`, `/auth/login`, `/auth/refresh`, `/auth/register`, docs endpoints, and
  `/invites/*`.
- R2 · Passwords hashed with scrypt, never stored or logged in plaintext.
- R3 · Role checked per route: `admin`, `manager`, `viewer`, `device`. Mutating camera control
  requires `admin` or `manager`.
- R4 · Tenant identity is taken from the **token**, never from the request path or body.
- R5 · Any route carrying a resource id must verify that resource belongs to the caller's tenant.
- R6 · Role and tenant are re-read from the database on every request so revocation is immediate.
- R7 · Login attempts are throttled: 8 failures per `host|username` per 5 minutes, then 429.
- R8 · An unset `SMART_CAM_TOKEN_SECRET` must fall back to a generated secret persisted on the
  data volume, never to a hardcoded default.
- R9 · Plan and billing fields are operator-only, gated on `SMART_CAM_PLATFORM_KEY`.

## 6. Interfaces

### 6.1 HTTP

- JSON in, JSON out. Errors are `{"detail": "..."}` with a meaningful status code.
- 401 unauthenticated · 403 wrong role · 404 not found **or not yours** (deliberately
  indistinguishable, to avoid confirming existence across tenants).
- Route families: `/auth/*`, `/tenants/*`, `/api/*`, `/device/*`, `/invites/*`, `/plans`.

### 6.2 WebSocket

| Endpoint | Purpose | Auth |
|---|---|---|
| `/ws/events` | Push new events for the caller's tenant | Access token |
| `/ws/webrtc/{source_id}` | SDP/ICE for live video | Access token + source ownership |

Both accept the token as a `bearer` subprotocol (keeps it out of proxy logs) and still accept
`?token=` for older clients.

### 6.3 Device ingest

`POST /api/ingest/events` (≤500 per call), `/api/ingest/occupancy` (≤2000), `/api/ingest/media/{event_id}`.
Device-authenticated; every row stamped with the device's tenant.

### 6.4 Uploads

Single file ≤ 2 GiB, extension whitelisted to image and video types, streamed with a running
byte counter so an oversized body is discarded rather than filling the disk.

## 7. Configuration and secrets

Configuration is a JSON document with typed sections: `SourceConfig`, `DetectionConfig`,
`EventConfig`, `ZoneConfig`, `PrivacyConfig`, `RetentionConfig`, `StorageConfig`, `AuthConfig`,
`WebhookConfig`, `ReportConfig`, `AlprConfig`, `FaceConfig`, `ReidConfig`,
`VLMSummarizerConfig`, `NotifyConfig`, `WebRTCConfig`, `AppConfig`.

Environment variables:

| Variable | Purpose |
|---|---|
| `SMART_CAM_CONFIG` | Config file path (must live on the volume) |
| `SMART_CAM_TOKEN_SECRET` | HMAC signing key |
| `SMART_CAM_ADMIN_PASSWORD` | Bootstrap admin password, first run only |
| `SMART_CAM_CORS_ORIGINS` | Allowed origins; defaults are permissive — **must be set in production** |
| `SMART_CAM_CLOUD_ONLY` | Disable the local pipeline (edge-only deployments) |
| `SMART_CAM_PLATFORM_KEY` | Required to change a tenant's plan |
| `COPILOT_API_KEY` / `COPILOT_BASE_URL` / `COPILOT_MODEL` | Co-pilot provider |

**Requirement:** secrets must never be committed, and must never enter an image layer.
`.dockerignore` excludes `config.json`, `.env*` and `.security-audit` for exactly this reason;
both Dockerfiles do `COPY . .`.

## 8. Deployment

**Topology:** one VPS. Caddy in host network mode terminates TLS and proxies; API and web
containers bind loopback only.

| Item | Value |
|---|---|
| Domain | `https://agay.tech` |
| Routing | `/smartapi/*` → API; else → Next.js |
| API bind | `127.0.0.1:8000` and `[::1]:8000` |
| Web bind | `127.0.0.1:3000` |
| Data volume | `/app/data` (database, config, clips, thumbnails, audit log) |
| Deploy | `scripts/deploy_api.sh`, `scripts/deploy_web.sh` |
| Registry | GHCR images for the web and API tiers |

**Deployment requirements**

- D1 · The deploy script must refuse to recreate a container whose `/app/data` is not on a volume.
- D2 · It must carry `config.json` across a rebuild, and roll back if the new container fails.
- D3 · Health verification must run on loopback so it works while the site is firewalled.
- D4 · It must be safe to re-run after an interruption (clear a stale rollback container).
- D5 · Firewall rules must be persisted (`netfilter-persistent`) — unsaved rules do not survive a
  reboot, and a reboot silently republishes the site.

## 9. Performance and capacity

| Metric | Target | Basis |
|---|---|---|
| Detection | ≥ 5 fps per source on CPU | Model size choice |
| Event latency | ≤ 5 s frame → dashboard | Pipeline + WebSocket poll interval (1 s) |
| API p95 | < 300 ms for list endpoints | Indexed queries |
| Concurrent WebRTC viewers | ~5 per source | aiortc relays frames per peer |
| Cameras per VPS | 25 (Pro tier limit) | CPU-bound |

**Known scaling limits:** in-memory login throttle assumes one API process; SQLite assumes one
writer; both need revisiting before horizontal scale-out.

## 10. Observability

Current state: application logging via the standard `logging` module; `audit.log` records
registrations, login outcomes and account changes; `docker logs` is the only aggregation.
**Gap:** no metrics, no alerting, no error tracking, no uptime monitor. Before paying customers,
add at minimum an external uptime check and disk-space alerting.

## 11. Security requirements and compliance status

| Requirement | Status |
|---|---|
| Per-tenant authorization on every id-bearing route | Met (hardened this session) |
| Immediate revocation | Met |
| Audit trail of administrative action | Met (partial coverage) |
| Upload bounds | Met |
| Plan/billing tamper-proofing | Met |
| CORS restricted in production | **Not met** — defaults to `*` |
| Encryption at rest for media | **Not met** — `privacy.encrypt_files` is a no-op |
| Co-pilot resistant to prompt injection | **Not met** |
| Stream concurrency limits | **Not met** |
| Certified security audit | **Not met** — run recorded as incomplete |

## 12. Technical constraints and debt

1. **Two databases, one schema.** DDL is shared; Postgres support is untested in production.
2. **Legacy Streamlit app** (`app.py`) duplicates the dashboard and is not tenant-scoped.
3. **Tenant stamping uses the process tenant**, not the caller, for some write paths.
4. **Streaming is unbounded** — `/api/stream` holds a worker per viewer indefinitely.
5. **No migration tool** — migrations are hand-listed in `_column_migrations()`.
6. **No test coverage for route authorization** — the suite has no HTTP/WS client fixture, so the
   fixes in §11 are unguarded against regression.
