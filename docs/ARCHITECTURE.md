# SmartCam → Multi-Tenant Web Product
## Architecture & Phased Roadmap

**Status:** Proposal (no code changes made yet). Author: engineering. Supersedes nothing; this is the first architecture doc.

---

## 1. Goal

Turn SmartCam from a single-machine Streamlit dashboard into a **multi-tenant SaaS** where many hotels ("tenants") each manage their own cameras, users, and rules — while detection/recording runs on an **on-site edge box per hotel** and a **cloud control plane** handles identity, notifications, summaries, and cross-site search.

The product frontend will be a **React / Next.js** single-page app consuming the existing **FastAPI** backend. Streamlit stays as an internal/admin console only.

---

## 2. Current state (accurate inventory)

What already exists and maps to a product:

- **API server** — `run_api.py` + `smartcam/api.py` (FastAPI). ~38 REST endpoints + `/ws/events` WebSocket + MJPEG `/api/stream/{id}`.
- **Remote client** — `smartcam/client.py` (`ApiClient`) driven by `SMART_CAM_API_URL`; a UI can already talk to a pipeline running elsewhere. This is the seed of the edge/cloud split.
- **Roles** — `admin / security / manager / viewer`, gated via `ROLE_TABS` in `app.py`.
- **Detection pipeline** — `CameraPipeline` + `PipelineManager`: YOLOv8 (now ONNX by default) + ByteTrack, zones, fall pose, abandoned object, ALPR (EasyOCR), face recognition (deepface Facenet), multi-camera ReID (torchreid OSNet), occupancy, heatmaps, retention, privacy blur, E2E-encrypted notifications (ntfy), webhooks, VLM summaries (OpenAI/Ollama).
- **Data** — SQLite (`smartcam/db.py`) with 8 tables (`events, plates, faces, face_matches, appearances, identities, sightings, occupancy_samples`) and `PRAGMA user_version` migrations.
- **Ops** — Dockerfile, docker-compose, systemd unit, `deploy/README.md`.

What is **missing** for a multi-user web product (the hard gaps):

1. **No server-side auth.** `smartcam/api.py` has zero auth dependency — every endpoint is open. `smartcam/auth.py` only checks a `config.json`-based user list using **unsalted SHA-256**, and the login gate lives only in the Streamlit app. Auth disabled currently returns role "admin" (full access).
2. **No tenancy.** One global `config.json`, one data dir, one `PipelineManager`. Nothing isolates hotel A from hotel B.
3. **Single-file SQLite.** Fine for one site; wrong for concurrent multi-tenant writes.
4. **Dashboard-first packaging.** Docker defaults to Streamlit with the pipeline in-process; a real product needs headless API + separate frontend.
5. **MJPEG streaming.** Bandwidth-heavy and single-viewer oriented; won't scale to many concurrent users/cameras.
6. **Weak password hashing.** SHA-256 (no salt, no KDF) must become Argon2id or bcrypt.

---

## 3. Target architecture

    ┌──────────────────────────────────────────────────────────────┐
    │                    CLOUD  (SaaS control plane)              │
    │                                                             │
    │  ┌─────────────────┐   ┌──────────────┐   ┌──────────────┐  │
    │  │  React/Next.js  │◄─►│  API Gateway │   │  Auth Service │  │
    │  │  Web App        │   │  (FastAPI)   │   │  (JWT/RBAC)   │  │
    │  └─────────────────┘   └──────┬───────┘   └──────────────┘  │
    │                               │                              │
    │  ┌────────────────────────────┴────────────────────────────┐ │
    │  │  Postgres: tenants, users, sites, devices, events,     │ │
    │  │  plates, faces, identities, occupancy (multi-tenant)   │ │
    │  │  Object storage: clips & thumbnails (S3/MinIO)         │ │
    │  │  VLM summaries, notifications, webhooks, search index  │ │
    │  └─────────────────────────────────────────────────────────┘ │
    └───────────────────────────────▲──────────────────────────────┘
                                     │  HTTPS outbound from edge
                                     │  events, thumbnails, occupancy,
                                     │  heartbeats; config/commands down
        ┌────────────────────────────┴──────────────────────────────┐
        │       EDGE BOX (one per hotel, on the camera LAN)         │
        │  CameraPipeline + PipelineManager (existing code)         │
        │  RTSP ingest · detection/tracking · recording · ALPR ·    │
        │  face · ReID · occupancy · zones · privacy blur           │
        │  Local SQLite + local clip ring buffer + offline queue    │
        └───────────────────────────────────────────────────────────┘

**Responsibilities**

- **Edge** owns the heavy lifting: video ingest, inference, tracking, recording, privacy blur, local rules, local retention. It is the only component that touches camera video directly.
- **Cloud** owns identity, tenants, billing, notifications, VLM summaries, and the cross-site search index. It never needs raw video (only event metadata + thumbnails + short clips on demand).
- **Edge initiates outbound connections** to cloud (no inbound ports, no NAT traversal headaches). This also makes it tolerant of hotel firewalls.

---

## 4. Key decisions (resolved forks)

| Decision | Choice | Rationale |
|---|---|---|
| Tenancy model | Multi-tenant SaaS (many hotels) | Chosen. One tenant = one hotel organization, many sites/cameras/users. |
| Deployment | Hybrid edge + cloud | Cameras are on hotel LANs; streaming all video to cloud is costly and slow. Edge keeps latency/bandwidth/privacy local. |
| Frontend | React/Next.js over FastAPI | Streamlit is a poor fit for per-user sessions, branding, and real-time scale. |
| AuthN | JWT (short-lived access + refresh) | Stateless, works for both browser users and edge devices (device tokens). |
| AuthZ | RBAC + tenant scoping | Extend existing roles; add tenant membership checks on every query. |
| Password hashing | Argon2id (or bcrypt) | Replace unsalted SHA-256. |
| Cloud DB | Postgres (SQLAlchemy + Alembic) | Multi-tenant concurrency, migrations. Edge keeps SQLite. |
| Streaming | WebRTC (MediaMTX/go2rtc); HLS/MSE fallback | Replace MJPEG for multi-viewer, low-latency live view. |
| Inference | ONNX (done) → OpenVINO on Intel edge | Free, faster on the i7-class boxes; GPU/TPU later. |

---

## 5. Gap analysis (current → target)

| Concern | Today | Target |
|---|---|---|
| API auth | None (open endpoints) | Every endpoint requires a JWT + RBAC check |
| User store | `config.json` + SHA-256 | `users` table, Argon2id, sessions |
| Tenancy | Single global config/data dir | `tenant_id` on every table; isolated |
| Data store | One SQLite file | Postgres (cloud) + SQLite (edge) |
| Frontend | Streamlit dashboard | Next.js SPA + Streamlit admin console |
| Streaming | MJPEG | WebRTC / HLS (MSE) |
| Camera reach | Assumes local access | Edge agent + outbound channel |
| Deployment | Dashboard-first Docker | Headless API + edge image + frontend host |
| Secrets | Env vars + config.json | Per-tenant secrets (KMS/Vault), device tokens |

---

## 6. Data model (multi-tenant)

Introduce a tenant dimension and a device/org hierarchy. Recommended early shape (Postgres, edge keeps a subset):

    tenants(id, name, slug, plan, created_at, status)
    users(id, tenant_id, email, password_hash, role, mfa, created_at)
    sites(id, tenant_id, name, timezone, address)
    devices(id, tenant_id, site_id, name, device_token_hash, last_seen, version)
    sources(id, tenant_id, site_id, device_id, uri, name, enabled, config)
    zones(id, tenant_id, source_id, ...)
    events(id, tenant_id, source_id, camera_id, ...)        -- + existing columns
    plates, faces, identities, sightings, occupancy_samples -- all gain tenant_id

Rules:

- Every row carries `tenant_id`; every query is filtered by the caller's tenant (app-level scoping first; Postgres RLS as a hardening step later).
- The **edge box** keeps its local SQLite schema and is seeded with `tenant_id` + `site_id` + a device token at provisioning.
- Clips/thumbnails move to object storage with **signed URLs**; the edge holds a short local ring buffer for low-latency playback and offline resilience.

---

## 7. Authentication & authorization

**Users (browser):**

1. Login returns an access JWT (claims: `user_id, tenant_id, role`) + a refresh token.
2. A FastAPI dependency validates the token and injects the principal; a second dependency enforces role/permission per route (e.g. `viewer` can read events, `admin` can manage sources/users).
3. Password reset, email verification, and MFA are P2+.

**Edge devices (machine):**

1. Provisioning issues a long-lived per-device token (not a user JWT).
2. The edge presents it over an outbound WebSocket/HTTPS channel; cloud maps it to `tenant_id + site_id + device_id`.

**Role matrix (extend the existing four roles):**

| Capability | viewer | security | manager | admin |
|---|---|---|---|---|
| View live / events / search | ✓ | ✓ | ✓ | ✓ |
| Acknowledge / resolve / assign alerts | – | ✓ | ✓ | ✓ |
| Configure cameras/zones/rules | – | – | ✓ | ✓ |
| Manage users & billing | – | – | – | ✓ |

---

## 8. Edge ↔ Cloud protocol

- **Upstream (edge → cloud):** heartbeats, health, event metadata, plate reads, face/ReID matches, occupancy samples, thumbnails, and short clips. Sent over an outbound WebSocket with a local **offline queue** that flushes on reconnect.
- **Downstream (cloud → edge):** config updates, start/stop camera, request a clip, software update, revoke device. Delivered over the same outbound channel (no inbound ports).
- **Security:** TLS everywhere; device tokens scoped to one device; cloud never receives full video streams unless a clip is explicitly requested.

---

## 9. Frontend plan (React/Next.js)

- **Pages:** login, tenant dashboard, live view (multi-camera grid), alerts, events (with scrubber/clip playback), smart search, analytics/occupancy, plates, faces, track-person, settings, admin (users/billing).
- **Realtime:** subscribe to `/ws/events` (already exists) for live alert/event updates.
- **Streaming:** WebRTC via MediaMTX/go2rtc for live; signed URLs for recorded clips.
- **Keep Streamlit** as the internal/admin/ops console during the transition (it already talks to the API via `ApiClient`).

---

## 10. Phased roadmap

### P0 — Harden backend into a real (single-tenant) service  *foundation*
- Add Postgres (SQLAlchemy + Alembic) for users/sessions; keep edge SQLite.
- Replace SHA-256 with Argon2id/bcrypt.
- Add JWT auth + RBAC + tenant scoping as FastAPI dependencies; enforce on **all** existing endpoints.
- Add `/auth/login`, `/auth/refresh`, `/auth/logout`, user CRUD (admin only).
- Replace MJPEG with WebRTC/HLS (spike MediaMTX or go2rtc).
- Keep Streamlit working by pointing it at the authenticated API (extend `ApiClient` to send tokens).

### P1 — Product frontend
- Stand up Next.js app over the existing API; implement login + core pages.
- Wire realtime via `/ws/events`.
- Retire Streamlit to internal/admin console.

### P2 — Multi-tenancy
- Add `tenant_id` to all tables; implement onboarding/registration, org + site + device model, invites, per-tenant config/secrets.
- Object storage (S3/MinIO) for clips/thumbnails with signed URLs.
- Billing stub (Stripe) + plan/usage metering (optional in P2).

### P3 — Edge + cloud split
- Package the existing pipeline as a provisionable edge agent with per-device tokens.
- Build the outbound ingest channel + offline queue + config push + remote start/stop/stream.
- Centralize notifications, VLM summaries, and cross-site search.

### P4 — Scale & ops
- OpenVINO (or GPU/TPU) acceleration on edge; resource limits per site.
- Retention lifecycle, monitoring/alerting, backups, autoscaling, GDPR/privacy controls per jurisdiction.

---

## 11. Risks & open questions

- **WebRTC complexity** (TURN/NAT, codec support) — de-risk with MediaMTX/go2rtc early.
- **Migration** of existing single-site SQLite data into the tenant model.
- **CPU-only inference** at scale → OpenVINO now, GPU later.
- **Bandwidth/storage cost** — informs retention defaults and clip resolution/fps.
- **Privacy/compliance** — the existing blur + consent + E2E-encryption features are strong selling points; keep them tenant-configurable.
- **Secrets management** — per-tenant API keys and device tokens need a vault/KMS.

---

## 12. Non-goals (near term)

- No custom ML training pipeline (use pretrained YOLOv8/OSNet/Facenet).
- No mobile app yet (the responsive Next.js web app covers phones; native apps later).
- No on-prem multi-box cluster per site (single edge box per site first).

---

## 13. Immediate next steps

1. Decide Postgres hosting (managed vs self-hosted) and object storage (S3/MinIO).
2. Implement the auth service: users table, Argon2id, JWT, and a FastAPI dependency — then enforce it on the existing API.
3. Stand up the Next.js skeleton + login page against the authenticated API.

*This document is a plan for review. No code has been changed to implement it yet.*
