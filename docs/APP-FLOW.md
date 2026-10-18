# App Flow — SmartCam

**Status:** Draft 1 · **Date:** 2026-10-17
Describes the real navigation and request flows in the committed frontend and API.

---

## 1. Actors

| Actor | Entry point | Lands on |
|---|---|---|
| Anonymous visitor | `/` (marketing site) | Landing page |
| Prospective customer | `/register` | Tenant created, dashboard |
| Invited user | `/invite/{token}` | Account created, dashboard |
| Returning user | `/login` | `/dashboard` |
| Admin | `/admin` | User and tenant management |
| Edge device | API only | — |

## 2. Entry flows

### 2.1 Self-serve registration — `POST /auth/register`

```
Visitor → /register
  → company, username, password
  → 429 if >5 signups from this host in an hour
  → 409 if slug or username taken
  → tenant created, admin user created, audit entry written
  → access + refresh tokens returned
  → redirected to /dashboard with an empty state
```

No email verification. The tenant works immediately.

### 2.2 Invited user — `/invite/{token}`

```
Admin creates invite (email, role) → token emailed/issued out of band
  → /invite/{token} preview shows tenant name and assigned role
  → user sets username + password
  → account created in the inviting tenant with the invited role
  → invite marked consumed; re-use returns 400
```

### 2.3 Login — `POST /auth/login`

```
/login → username + password
  → 429 after 8 failures per host+username in 5 minutes
  → 401 on bad credentials (audit: login.fail)
  → success: access (12 h) + refresh (30 d), audit: login.ok
  → /dashboard
```

Token stored in `localStorage`; every request attaches `Authorization: Bearer …`. A 401 mid-session
bounces to `/login`.

## 3. Operator flows

### 3.1 Dashboard — `/dashboard`

Landing surface after login. Shows live event feed, open alerts and inspection counters.
The feed subscribes to `/ws/events` and prepends new items as they arrive, capped at 15 in view.
WebSocket authenticated by a `bearer` subprotocol.

```
useEffect → token present? → open WS
   → onmessage: prepend event to the feed
   → onclose: retry after 4 s unless the component unmounted
```

### 3.2 Live view — `/live`

Two paths, chosen by capability:

```
/live → GET /api/webrtc/config
   ├─ enabled → WebRTC: WS /ws/webrtc/{source_id} → SDP offer/answer → ICE → <video>
   └─ disabled → MJPEG: <img src="/api/stream/{source_id}">
```

Both paths enforce source ownership server-side. A viewer sees only cameras belonging to their
tenant; cameras with no `tenant_id` are shared demo feeds visible to all.

### 3.3 Alert triage — `/alerts`

The core operational loop:

```
Open alert
  → thumbnail + clip + AI summary + camera + time
  → user action:
       Ack      → POST /api/ack/{event_id}       → leaves the open queue
       Resolve  → POST /api/resolve/{event_id}   → closes with a disposition
       Assign   → POST /api/assign/{event_id}    → owner recorded
       Escalate → POST /api/escalate/{event_id}  → flagged upward
  → every action is tenant-checked; a cross-tenant id returns 404
```

### 3.4 Event search — `/search` and `/events`

- `/events` — chronological list, filterable by camera, type, order.
- `/search` — natural-language or keyword query via `/api/search`, returning matching events with
  relevance ordering.

### 3.5 Recognition surfaces

| Page | Reads | Writes |
|---|---|---|
| `/plates` | `/api/plates` | — |
| `/faces` | `/api/faces`, `/api/face_matches` | `POST/DELETE /api/faces`, `POST /api/delete_person` |
| `/track` | `/api/identities`, `/api/sightings/{id}` | `POST/DELETE /api/identities` |

Deleting a person resolves the face **inside the caller's tenant first**, then cascades to
matches, identity and sightings.

### 3.6 Analytics — `/analytics`

Occupancy history, heatmap and counts: `/api/occupancy_history`, `/api/heatmap/{id}`, `/api/count`.

### 3.7 Import — `/import`

Upload an existing video file for offline analysis: `POST /api/upload` (≤ 2 GiB, whitelisted
extension) → path returned → registered as a source.

### 3.8 Administration — `/admin`

```
/auth/users  → list (own tenant only)
             → create (tenant forced to the caller's; a supplied tenant_id is ignored)
             → update role / reset password (own tenant only)
             → delete (own tenant only)
/tenants/{id}/sites, /devices, /invites → caller's own tenant only; anything else is 404
```

### 3.9 Settings — `/settings`

Eight tabs: Cameras · Zones · Detection · Alerts & clips · Live video · Storage & privacy ·
Notifications · Recognition. Reads `GET /api/config`, writes `PUT /api/config`
(admin/manager only). Camera add/remove live here.

### 3.10 Co-pilot — the Vera drawer

Available throughout the app as a drawer.

```
Question typed in the drawer
  → POST /copilot  (Next.js route, NOT /api/* — Caddy sends /api/* to Python)
  → bearer token checked only for presence
  → provider resolves from COPILOT_* env, falling back to /api/config
  → agent loop, max 4 steps, 7 tools:
       events, alerts, occupancy, plates, faces, identities, config
  → answer returned with the tool results it was grounded on
```

**Known weakness:** event `camera_name` and `summary` are device-controlled text that reaches the
model context, so a compromised edge device could attempt indirect prompt injection.

## 4. Device flow

```
Admin: POST /tenants/{id}/devices → returns a device token (single display)
Device on site:
   → Authorization: Device <token>
   → POST /device/heartbeat          (liveness, last_seen)
   → POST /api/ingest/events         (≤500 detections per call)
   → POST /api/ingest/occupancy      (≤2000 samples per call)
   → POST /api/ingest/media/{id}     (clip and/or thumbnail)
Rotation: POST /tenants/{id}/devices/{device_id}/rotate-token bumps the generation, which
invalidates the previous token immediately.
```

## 5. Tenant isolation model

Enforced on four axes, all derived from the token rather than the request:

1. **Events and media** — `_event_for_tenant`; foreign ids return 404.
2. **Cameras** — `_tenant_can_see_source`; `tenant_id IS NULL` means shared demo feed.
3. **Tenant-scoped routes** — `_require_own_tenant` on all twelve `/tenants/{id}/…` routes.
4. **Users and biometrics** — `_require_user_in_tenant`, plus ownership resolution before delete.

Choosing 404 over 403 is deliberate: a wrong-tenant id is indistinguishable from a missing one, so
the API never confirms that another tenant's record exists.

## 6. Failure and edge flows

| Condition | Behaviour |
|---|---|
| Token expired mid-session | 401 → client bounces to `/login` |
| Role changed or account deleted | Next request 401 — revocation is immediate |
| API container down | Caddy returns 5xx; the dashboard shows an error state |
| WebSocket drops | Client retries every 4 s while the component is mounted |
| AI provider unavailable | Co-pilot returns an error; detection and events are unaffected |
| Upload exceeds 2 GiB | 413, partial file deleted |
| Signup flood | 429 after 5 per host per hour |
| Login brute force | 429 after 8 failures per host+username in 5 minutes |
| Camera offline | `/api/status` reports health; the pipeline does not crash the API |
