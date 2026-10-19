# Product Requirements Document — SmartCam

**Status:** Draft 1 · **Date:** 2026-10-17 · **Owner:** Founder
**Audience:** founder, any developer or designer joining the project

---

## 1. Summary

SmartCam is a multi-tenant AI video surveillance platform. Commodity IP cameras feed a
YOLOv8 detection pipeline; the platform turns detections into searchable events, alerts,
occupancy trends, licence-plate reads and person re-identification, and exposes them through a
web dashboard with an AI co-pilot.

The product is built and deployable. The market is **gated estates and hotels**, starting in
Nigeria. A Canadian long-term-care product is planned separately, as an independent codebase in
its own repository — it is **out of scope here**, and nothing in this document applies to it.

## 2. Problem

Small and mid-sized sites run cameras that record continuously and are watched by nobody.
Footage is reviewed only after an incident, by scrubbing hours of video. Existing video
management systems are either enterprise-priced and installer-locked, or consumer toys with no
multi-site story and no reporting.

The gap: **affordable, self-serve, multi-site video intelligence that tells staff what happened
instead of asking them to watch.**

## 3. Target users

| Persona | Role | Needs | Today |
|---|---|---|---|
| **Operations manager** | Owns safety across one or more sites | Know what happened, when, where; prove it with a clip | Scrubs footage reactively |
| **Front-desk / duty staff** | First responder to an alert | Fast triage: see the event, acknowledge, escalate | Gets an alert with no context |
| **Owner / administrator** | Runs the account | Manage users, cameras, plans, retention | Spreadsheet and a phone call to the installer |
| **Edge device** | Software on the site | Push detections and media upstream reliably | Not a human actor, but a first-class principal |

**Hotels (Nigeria).** 20–200 cameras. Buying trigger: theft, guest disputes, staff accountability,
car-park control. Constraints: intermittent connectivity, price sensitivity, no in-house IT.

**Gated estates (Nigeria).** A perimeter, a gatehouse and shared facilities, managed on behalf of
a residents' association. Buying trigger: intrusion, perimeter loitering, unknown vehicles,
contractor oversight. The association's demand for documented incidents is what the event and
clip history exists to satisfy.

Both are served by the same feature set, and that is not a coincidence: the zone rules are
`loitering`, `queue`, `intrusion` and `parking` with vehicle capacity counting; ALPR runs on
vehicles inside parking zones; the default camera is named "Lobby". The code was built for these
two buyers.

**Out of scope:** long-term care, healthcare, and any deployment governed by Canadian or health
privacy law. That is a separate product in a separate repository.

## 4. Jobs to be done

1. *When an alert fires, tell me what happened in one glance so I can act in seconds.*
2. *When something is disputed, find the clip by describing it rather than scrubbing.*
3. *When I run several sites, show me all of them without a separate login.*
4. *When I add a camera, do it without a technician.*
5. *When a regulator or insurer asks, produce a record of incidents.*
6. *When staff leave, remove their access immediately.*

## 5. Capability scope and status

Status reflects the committed source: **Built** = working end-to-end; **Partial** = present but
incomplete or unverified; **Stub** = data model only; **Absent** = not started.

### 5.1 Detection and events

| # | Requirement | Status | Notes |
|---|---|---|---|
| E1 | Object detection (person, vehicle, etc.) on live RTSP/USB/webcam sources | Built | YOLOv8 + ByteTrack |
| E2 | Event assembly from tracks with clip + thumbnail capture | Built | |
| E3 | Event list, filter, order | Built | `/api/events` |
| E4 | AI-generated natural-language event summary | Built | Optional VLM provider |
| E5 | Acknowledge / resolve / assign / escalate lifecycle | Built | |
| E6 | Zone-based filtering and intrusion rules | Built | `/api/zones/{source_id}` |
| E7 | Occupancy counting and history | Partial | Aggregate endpoint not tenant-filtered (see audit) |
| E8 | Heatmaps | Partial | Endpoint exists |

### 5.2 Search and recognition

| # | Requirement | Status | Notes |
|---|---|---|---|
| S1 | Semantic/keyword search over events | Built | `/api/search` |
| S2 | Licence-plate recognition and plate log | Built | Separate model |
| S3 | Face recognition with a consented gallery | Built | Embeddings stored |
| S4 | Person re-identification across cameras | Built | `/api/embed_reid`, identities/sightings |
| S5 | Biometric consent tracking | Partial | `faces.consent` column exists; no workflow enforces it |

### 5.3 Live video

| # | Requirement | Status | Notes |
|---|---|---|---|
| L1 | MJPEG fallback stream | Built | `/api/stream/{id}` |
| L2 | WebRTC low-latency stream | Built | aiortc, optional TURN |
| L3 | Real-time event push to the dashboard | Built | WebSocket |

### 5.4 Multi-tenancy and administration

| # | Requirement | Status | Notes |
|---|---|---|---|
| A1 | Tenant → site → device hierarchy | Built | |
| A2 | Roles: admin, security, manager, viewer; device is a separate token principal | Built | `security` is the operational role — triage without configuration |
| A3 | Per-tenant data isolation | Built | Hardened this session; see §7 |
| A4 | User management, invites | Built | |
| A5 | Device enrolment and token rotation | Built | |
| A6 | Immediate revocation on role change or deletion | Built | Added this session |
| A7 | Plans and usage metering | Stub | `smartcam/billing.py` |
| A8 | Payment processing | Absent | No Stripe integration |

### 5.5 AI co-pilot ("Vera")

| # | Requirement | Status | Notes |
|---|---|---|---|
| C1 | Natural-language questions over the tenant's data | Built | 7 tools, max 4 reasoning steps |
| C2 | Provider-agnostic (OpenAI-compatible) | Built | `COPILOT_*` env |
| C3 | Grounded answers only, no invented events | Partial | Relies on system prompt |
| C4 | Prompt-injection resistance against camera-controlled text | Absent | Open finding |

### 5.6 Edge and integration

| # | Requirement | Status | Notes |
|---|---|---|---|
| I1 | Edge agent that runs on-site and pushes upstream | Built | `edge_agent.py` |
| I2 | Batch ingest of events, occupancy, media | Built | `/api/ingest/*` |
| I3 | Cloud-only mode (no local pipeline) | Built | `SMART_CAM_CLOUD_ONLY` |
| I4 | Webhooks / third-party notifications | Partial | Config section exists |

## 6. Non-functional requirements

| Area | Requirement |
|---|---|
| **Latency** | Alert on dashboard within 5 s of the triggering frame; WebRTC under 1 s glass-to-glass |
| **Throughput** | 25 cameras per deployment on one mid-size VPS |
| **Availability** | Single-VPS, best effort in P0; graceful degradation if the AI provider is down |
| **Durability** | Events survive container recreation; media on a mounted volume |
| **Privacy** | Tenant data never crosses tenants; biometric deletion must actually delete |
| **Compliance** | Retention controls; consent record for biometrics; audit trail of administrative action |
| **Portability** | SQLite by default, Postgres-ready DDL |

## 7. Security posture (as of this document)

This session closed the highest-severity gaps. Still open, and therefore **not yet
launch-ready for paying customers**:

- `/api/stream` has no cap on concurrent streams (availability)
- `privacy.encrypt_files` is a toggle that performs no encryption
- CORS defaults to `*` when unconfigured
- Records are stamped with the process tenant, not the calling tenant
- Co-pilot input can be influenced by camera-controlled text (indirect prompt injection)
- No certified security audit has been completed; the six-phase run is recorded as incomplete

## 8. Success metrics

| Metric | Target | Why |
|---|---|---|
| Time to first alert after signup | < 15 min | Self-serve promise |
| Alerts triaged within 5 min | > 80% | Product is about response, not storage |
| Weekly active sites per account | > 70% | Retention proxy |
| Storage cost per camera-month | Tracked | Gross margin driver |
| Paying tenants | 20 in 2 months (Segment A target) | Original GTM goal |

## 9. Open product decisions

1. **Pricing and packaging.** Free/Pro/Enterprise tiers are defined in code but no payment path
   exists. An estate and a hotel buy differently — per gate or per unit versus per room.
2. **On-premise vs hosted.** `SMART_CAM_CLOUD_ONLY` exists but the commercial model for
   on-premise is undefined. Intermittent connectivity makes this a live question, not a
   hypothetical.
3. **This product has no marketing site.** Everything the repository had was written for the other
   product and has been removed. Hotels and estates need their own, and it is the largest remaining
   piece of work before a relaunch.

## 10. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| A second product splits focus | Neither ships well | The care product is a separate repo with its own scope and its own clock |
| Estate buying is committee-led | Slow decision, unclear owner | Sell to whoever owns security today, not the association |
| Connectivity at the site | Missed events, support load | Edge buffering; verify reconnect behaviour before the first pilot |
| Single VPS, no redundancy | Outage loses trust | Backups + documented restore |
| Security debt | Breach destroys a young brand | Finish the audit backlog before launch |
| Founder bandwidth | Everything is single-threaded | Ruthless scope |
