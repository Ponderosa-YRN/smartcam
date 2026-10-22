# App Flow Document — SmartCam
**Version 2.0 · reflects commit `f6b27ea`**

---

## 1. Actors

| Actor | Entry | Lands on |
|---|---|---|
| Platform operator (you) | API with platform key | Provisions tenants |
| Hotel / estate admin | `/login` | `/dashboard` |
| Duty guard (`security`) | `/login` | `/dashboard` → triage |
| Viewer (owner, association) | `/login` | Read-only |
| Invited user | `/invite/{token}` | Account created |
| Edge device | API only | — |

**There is no public sign-up.** `/register` was removed; the API route returns 403 unless the env flag is set.

---

## 2. Onboarding a customer — the operator flow

```
Admin → Tenants → slug, display name, first admin username + password
  → tenant created, admin created, both audited
  → invite the site's staff from Admin → Invites
```

A tenant without an admin is a dead end, so the form collects one.

---

## 3. Staff invite

```
Admin → Invites → pick tenant, email, role → "Send invite"
  → response contains https://agay.tech/invite/<token>   (nothing is emailed)
  → you send the link yourself
  → recipient opens it: "You have been invited to join <tenant> as <role>"
  → sets username + password → lands in the dashboard
```

7-day expiry, single use, revocable. **The link is the credential** — treat it like a password.

---

## 4. Adding cameras

```
Settings → Cameras → + Add camera → name, stream URL → Save
  → PUT /api/config returns {"restart_required": true}
  → docker restart smartcam        ← without this the camera has no pipeline
  → camera appears as running; Live shows it
```

There is no ONVIF discovery: every camera is a hand-typed RTSP URL, normally the sub-stream
(`/Streaming/Channels/102` on a Hikvision NVR).

---

## 5. Live view

```
/live → GET /api/sources (every 10 s)
   ├─ Snapshot mode (default): CameraFrame polls /api/frame/{id} every 2 s
   └─ Realtime mode: /ws/webrtc/{id} → SDP/ICE → <video>
```

A failed frame fetch keeps the last image, so a dead camera shows a frozen picture — the health badge
is what tells the truth.

---

## 6. Detecting and triaging

```
Frame → detect + track → zone rules / fall / ALPR / face / re-ID
  → event written with clip + thumbnail (+ summary when a VLM is configured)
  → /ws/events pushes it to the caller's tenant
  → appears in Open alerts and the dashboard feed
```

Triage actions, each audited and tenant-checked:

| Action | Endpoint |
|---|---|
| Acknowledge | `POST /api/ack/{id}` |
| Resolve | `POST /api/resolve/{id}` |
| Assign | `POST /api/assign/{id}` |
| Escalate | `POST /api/escalate/{id}` |

**Evidence hand-off:** Events → **Report** downloads a one-page PDF (camera, time, objects,
confidence, plate, status, assignee, frame, summary). This is the artefact an estate gives to police
or a residents' association.

---

## 7. Video import — the one-off assessment

```
/import → choose file, "Import and analyse"
  → POST /api/upload            (≤2 GiB, whitelisted extension)
  → POST /api/sources           (camera id "import_<ts>", loop=false, fast=true)
  → POST /api/start/{id}
  → polls /api/status/{id} every 1 s and shows frames
  → on finish: /api/events?camera_id=<import id>
```

Requires the full pipeline image. On the control-plane image this fails with
`503 source management is not available in cloud-only mode` — by design, not a bug.

---

## 8. Co-pilot

```
Drawer → question → POST /copilot (Next.js route; deliberately not /api/*, which Caddy sends to Python)
  → bearer token forwarded → provider resolved from COPILOT_* env, else /api/config
  → agent loop, max 4 steps, 7 tools, every call made with the caller's token
  → answer cites event numbers and times
```

Device-supplied camera names and summaries are sanitised and length-capped before reaching the model,
and the system prompt states that tool results are data, never instructions.

---

## 9. Recognition and the consent gate

```
Settings → Recognition → enable face recognition
  → PUT /api/config checks privacy.biometrics_consent
      ├─ absent → 400 with an explanation; nothing is saved
      └─ present → saved, audited as biometrics.enabled
  → "restart_required" → restart
```

Ticking consent alone audits `biometrics.consent` and enables nothing.

---

## 10. Edge deployment

```
Box at the site: edge_agent.py --api-url https://agay.tech/smartapi --token scd_… --config config.json
  → runs the pipeline locally against LAN cameras
  → buffers events in local SQLite (survives uplink loss)
  → pushes events, clips and occupancy every 15 s
  → heartbeat keeps the device row fresh
```

Outbound only: no port forwarding, no tunnel. Remove the same cameras from the cloud config or every
event is produced twice.

---

## 11. Tenant isolation — the rule everywhere

| Surface | Rule |
|---|---|
| Events and media | `_event_for_tenant`; foreign ids are 404 |
| Cameras | `_tenant_can_see_source`; `tenant_id IS NULL` is a shared demo feed |
| `/tenants/{id}/…` | `_require_own_tenant` on all twelve routes |
| Users | `_require_user_in_tenant` |
| Added cameras | Stamped with the caller's tenant |
| Occupancy | Aggregated only over the caller's cameras |

404 over 403 is deliberate: the API never confirms another tenant's record exists.

---

## 12. Failure behaviour

| Condition | Behaviour |
|---|---|
| Token expired | 401 → `/login` |
| Role changed or account deleted | Next request 401 — immediate |
| Camera offline | Health badge goes red; last frame stays on screen |
| Power cut | Recording stops; **nothing alerts** (gap) |
| Disk >85% | Telegram, once a day |
| Site not rendering | Telegram within 5 minutes |
| Whole box down | **Nothing** — the checker lives on the box |
| Upload >2 GiB | 413, partial file deleted |
| Biometrics without consent | 400 on save |
```
