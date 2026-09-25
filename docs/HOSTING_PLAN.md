# SmartCam — Web Hosting & Migration Plan

Status: plan (nothing deployed yet). Companion to docs/ARCHITECTURE.md and
docs/DEMO_CHECKLIST.md. This is the forward roadmap for turning the current
single-box app into a hosted multi-tenant SaaS serving Nigerian hotels.

## 1. Target architecture (hybrid edge + cloud)

- **Edge boxes** (one per hotel): run edge_agent.py — YOLO detection on-site,
  streaming events + clips + occupancy + heartbeats to the cloud with a device
  token. Raw video stays on-site (privacy + bandwidth win).
- **Cloud control plane** (stateless): FastAPI (REST + WebSocket signaling +
  MJPEG + WebRTC) plus the Next.js frontend.
- **State/storage**: PostgreSQL (tenants, users, events, alerts, plates, faces,
  occupancy) plus an S3-compatible object store (clips/thumbs).
- **Real-time**: WebSocket event feed + WebRTC signaling; a TURN relay (coturn)
  for WebRTC behind hotel NAT.
- **Optional cloud overflow**: containerized detection workers for hotels that
  do not run an edge box.

## 2. Recommended first deployment (right-sized for <50 cams / <10 viewers)

| Layer | Choice | Why |
| --- | --- | --- |
| API (FastAPI) | Fly.io — region london or amsterdam | closest good region to Nigeria, managed, WebSocket-friendly |
| Frontend (Next.js) | Vercel | global edge, zero-ops |
| Database | Fly Postgres (managed) | managed backups, minimal ops |
| Clips/thumbs | Cloudflare R2 | S3-compatible (code already supports it), free egress |
| TURN | coturn on a small Fly.io app | WebRTC behind hotel NAT |
| Detection | edge boxes at hotels (+ optional cloud workers) | already built (edge_agent) |

Equally valid alternative: AWS eu-west-2 (London) with RDS Postgres + S3 + ECS
Fargate. Start on Fly.io; the app is Docker/Postgres/S3, so moving to AWS later
is low-cost.

## 3. The real work (ordered migration checklist)

"Hosting" is the easy part — making the monolith cloud-ready is the work.

1. **SQLite to PostgreSQL** — replace the raw-sqlite3 EventStore with SQLAlchemy
   Core (SQLite stays as the test backend; switch via DATABASE_URL). Biggest and
   highest-leverage item.
2. **Storage to S3/R2** — mostly done (StorageConfig + S3Storage); just point
   provider=s3 and bucket at R2.
3. **Externalize secrets** — replace the file-based master token secret with a
   real secret store (derive_tenant_secret() is already the swap point).
4. **Stateless API + worker split** — run the API without the in-process
   pipeline; detection lives on edge/workers (edge agent done; add cloud worker
   mode).
5. **Real-time scaling** — Redis pub/sub for multi-instance WebSocket fan-out;
   TURN for WebRTC (only needed past one API instance).
6. **Billing** — Paystack or Flutterwave (Stripe does not onboard Nigerian
   merchants).
7. **Observability + reliability** — structured logs, uptime monitoring, DB
   backups, TLS, CI/CD (GitHub Actions build-and-push the image).

## 4. SQLite to Postgres specifics (the hard one)

SQLite-specific things today in smartcam/db.py:

- sqlite3 module + Row factory.
- Question-mark (?) placeholders — psycopg wants %s; SQLAlchemy text() with
  named params handles both dialects.
- PRAGMA user_version for migrations — Postgres has no PRAGMA; use a
  schema_migrations table instead.
- AUTOINCREMENT — Postgres uses SERIAL or GENERATED ... AS IDENTITY.
- JSON stored as TEXT via json.dumps — Postgres should use JSONB.
- lastrowid — Postgres uses RETURNING id.

Migration approach: put SQLAlchemy Core behind EventStore, keep a sqlite:///
test target so the 39-test suite keeps passing, then flip DATABASE_URL to
postgresql+psycopg:// for production. Steps:

1. Install sqlalchemy + psycopg[binary].
2. Add DATABASE_URL config (default sqlite:///data/events.db).
3. Rewrite EventStore methods on SQLAlchemy (engine, text() queries, named params).
4. Port _SCHEMA + _column_migrations to dialect-neutral DDL (or a one-time Alembic migration).
5. Verify pytest green on SQLite, then smoke-test against a real Postgres.

## 5. Cost estimate (small scale)

| Item | Monthly |
| --- | --- |
| Fly.io API (1-2 small VMs) | ~$10-25 |
| Fly Postgres | ~$15-30 |
| Cloudflare R2 | ~$0-5 (free egress) |
| Vercel (hobby) | $0-20 |
| TURN (small VM) | ~$3-6 |
| **Total cloud** | **~$30-85/mo** |
| Edge box per hotel (one-time) | ~$100-250 |

## 6. Nigeria specifics (must-read)

- No AWS/GCP/Azure region in Nigeria. Closest: AWS af-south-1 (Cape Town), Azure
  South Africa North (Joburg). In practice Europe (London/Frankfurt) usually has
  the best Lagos-to-cloud latency (~100-150ms) and the richest services.
- Live video is P2P (WebRTC) or edge-streamed, so server location barely affects
  the video itself — only API/signaling latency.
- Billing: use Paystack or Flutterwave, not Stripe.
- CDN: Cloudflare has strong West-Africa edge coverage; serve the frontend and
  clips through it.
- Data residency: if EU guests are involved, prefer an EU region + on-premise raw
  video (already the edge model).

## 7. Deployment runbook (draft)

Dockerfile skeleton:

    FROM python:3.11-slim
    WORKDIR /app
    COPY . .
    RUN pip install --no-cache-dir -r requirements.txt
    CMD ["uvicorn", "run_api:app", "--host", "0.0.0.0", "--port", "8080"]

Environment variables:

    DATABASE_URL=postgresql+psycopg://user:pass@host:5432/smartcam
    SMART_CAM_S3_BUCKET=...
    SMART_CAM_S3_ENDPOINT_URL=https://<account>.r2.cloudflarestorage.com
    SMART_CAM_S3_ACCESS_KEY=...
    SMART_CAM_S3_SECRET_KEY=...
    SMART_CAM_TOKEN_SECRET=...
    SMART_CAM_TURN_URL=...
    SMART_CAM_TURN_USERNAME=...
    SMART_CAM_TURN_CREDENTIAL=...
    SMART_CAM_CORS_ORIGINS=https://yourfrontend.com

Note: a requirements.txt does not exist yet — freeze the venv into one before
building the image.

## 8. Done vs pending

Done: edge agent + device tokens + ingestion, S3 storage backend, per-tenant
secrets seam, billing stub, WebRTC + STUN/TURN config, worker pool, device
abstraction.

Pending: SQLite-to-Postgres, secret-store integration, Redis pub/sub, cloud
worker mode, Paystack/Flutterwave billing, observability, CI/CD.
