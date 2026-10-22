# Product Requirements Document — SmartCam
**Version 2.0 · reflects commit `f6b27ea`**

An AI video surveillance platform for **hotels and gated estates in Nigeria**. It runs on cameras a
site already owns, turns detections into documented incidents, and hosts many customers on one
deployment.

**At this commit:** 78 API routes · 15 tables · 64 tests · ~5,500 lines of Python · one VPS.

Status: **Built** · **Partial** · **Not built**

---

## 1. Features, one by one

### 1.1 Detection and events

| ID | Feature | Status | Behaviour and limits |
|---|---|---|---|
| D1 | Object detection | Built | YOLOv8n, 80 COCO classes; triggers on person, car, truck, bus, motorcycle, bicycle |
| D2 | Multi-object tracking | Built | ByteTrack; stable ids per person/vehicle |
| D3 | Event assembly | Built | Track that triggers becomes an event with times, objects, confidence |
| D4 | Clip + thumbnail capture | Built | Per event; local disk or S3 |
| D5 | AI event summary | Built | Optional VLM provider; silent if unconfigured |
| D6 | Event list + filters | Built | By camera, type, order; tenant-scoped |
| D7 | Search over events | Built | Event records, not raw footage |
| D8 | **Fire / smoke detection** | **Not built** | No such class in COCO; needs a trained model |

### 1.2 Zones and rules

| ID | Feature | Status | Behaviour |
|---|---|---|---|
| Z1 | Polygon zones | Built | Drawn per camera in Settings |
| Z2 | Intrusion | Built | Object enters a zone |
| Z3 | Loitering | Built | Dwell beyond a threshold |
| Z4 | Queue | Built | Count against capacity |
| Z5 | Parking capacity | Built | Vehicles vs capacity |
| Z6 | Abandoned object | Built | Stationary object beyond a threshold |
| Z7 | Possible fall | Built | Torso angle ≥ 55° for 2 s, pose-first with box-ratio fallback. **Never described as fall detection** |
| Z8 | Time windows | Built | Rules active only within hours |

### 1.3 Recognition

| ID | Feature | Status | Behaviour |
|---|---|---|---|
| R1 | Licence plate reading | Built | Crop retained; plate log queryable |
| R2 | Face recognition | Built | **Off by default**; requires acknowledged lawful basis (§6) |
| R3 | Cross-camera re-ID | Built | **Off by default**; same consent gate |
| R4 | Occupancy — live | Built | People and vehicles in frame, per tenant |
| R5 | Occupancy — history | Built | Sampled series, tenant-scoped |
| R6 | **Daily in/out totals** | **Not built** | Existing counters count track appearances per camera, not threshold crossings. Deliberately withheld (§4) |

### 1.4 Evidence and triage

| ID | Feature | Status | Behaviour |
|---|---|---|---|
| E1 | Alert lifecycle | Built | Acknowledge, resolve, assign, escalate; all audited |
| E2 | Alert queue | Built | new / acknowledged / escalated |
| E3 | **Incident report PDF** | Built | One A4 page: camera, time, objects, confidence, plate, status, assignee, frame, summary. Tenant-checked |
| E4 | Clip playback | Built | In-page |
| E5 | Sharing with third parties | Partial | PDF download only; no share link, no bulk export |

### 1.5 Live view

| ID | Feature | Status | Behaviour |
|---|---|---|---|
| L1 | Snapshot mode | Built | Polls a JPEG every 2 s — the default mode |
| L2 | Realtime mode | Built | WebRTC (aiortc); needs a running pipeline |
| L3 | MJPEG stream | Built | Capped at 20 concurrent viewers |
| L4 | Camera health badge | Built | ok / warn / danger |

### 1.6 Co-pilot ("Vera")

| ID | Feature | Status | Behaviour |
|---|---|---|---|
| C1 | Natural-language query | Built | 7 tools, max 4 steps, provider-agnostic |
| C2 | Grounded answers | Built | Cites event numbers and times |
| C3 | Injection resistance | Partial | Device text sanitised and capped; model told tool output is data |

### 1.7 Tenancy and administration

| ID | Feature | Status | Behaviour |
|---|---|---|---|
| A1 | Tenant → site → device | Built | |
| A2 | Roles | Built | admin > manager > security > viewer; device is a token principal, not a role |
| A3 | Tenant isolation | Built | Every id-bearing route; 13 regression tests |
| A4 | Invitation-only onboarding | Built | 7-day single-use links; no self-signup |
| A5 | Provisioning with first admin | Built | A new customer is a tenant someone can log into |
| A6 | Immediate revocation | Built | Role and tenant re-read per request |
| A7 | Audit trail | Built | Registrations, logins, account changes, biometric consent, report generation |
| A8 | Plans and usage metering | Partial | Limits defined, **not enforced** |
| A9 | Payment | **Not built** | Manual invoicing only |

### 1.8 Notifications

| ID | Feature | Status | Behaviour |
|---|---|---|---|
| N1 | Multi-channel alerts | Built | Apprise, one URL per line — email, push, SMS gateways |
| N2 | **WhatsApp** | **Not built** | Needs Meta Business approval or a gateway |

### 1.9 Deployment and operations

| ID | Feature | Status | Behaviour |
|---|---|---|---|
| O1 | Single-origin HTTPS | Built | Caddy; API and web on loopback |
| O2 | Edge agent | Built | Detection on-site, local buffer, events upstream |
| O3 | Video import | Built | Upload once, analyse, report |
| O4 | Backup + verified restore | Built | `VACUUM INTO`; `--check` proves an archive |
| O5 | Disk + site monitoring | Built | Hourly disk, 5-minute site check, both to Telegram |
| O6 | **External uptime monitoring** | **Not built** | Nothing outside the box can report the box down |

---

## 2. Non-functional requirements

| Area | Requirement | Actual |
|---|---|---|
| Detection rate | ≥5 fps per source on CPU | Met for a few sub-streams |
| Event latency | ≤5 s frame → dashboard | Met |
| Tenant isolation | No cross-tenant read | Met, tested |
| Upload bound | Reject oversized bodies | 2 GiB |
| Retention | Configurable, 30-day default | Met |
| Backup | Restorable, proven | Met |
| Scale | 25 cameras per deployment | **Unmeasured**; CPU-bound |

---

## 3. Nigerian compliance position

| Requirement (NDPA / GAID) | Status |
|---|---|
| Recorded lawful basis for biometrics | **Built** — consent gate, audited |
| Retention limits | Built — 30-day default |
| Access limitation and roles | Built |
| Audit of personal-data access | Partial — reports and account changes logged, ordinary reads not |
| **DPIA filed with NDPC** | **Not done** — paperwork |
| **Transparency signage** | **Not done** |
| **Data subject request handling** | **Not built** |
| **Nigerian data residency** | **Not met** — hosted abroad |

**The product is not NDPA-compliant today, and no feature listed here changes that.** Penalty ceiling is ₦10,000,000 or 2% of annual gross revenue.

---

## 4. Deliberate non-features

| Withheld | Why |
|---|---|
| Daily in/out totals | The counters measure per-camera track appearances; a guest passing three cameras counts three times and they reset on restart. A number a hotelier can disprove is worse than no number |
| Fire/smoke | No class exists. Half-working fire alerts train staff to ignore alerts |
| Face recognition on by default | Creates liability for the customer and for you |

---

## 5. Risks

| Risk | Consequence |
|---|---|
| Face recognition exists at all | A customer enabling it without signage carries the legal risk; you carry the reputational one |
| "Possible fall" read as fall detection | Over-promising |
| No external monitoring | Outages are found by customers |
| Single VPS | One machine is the whole product |
| **AGPL-3.0 detector** | Unresolved commercial obligation |

---

## 6. Acceptance criteria — biometric consent gate

- Enabling `face` or `reid` without `privacy.biometrics_consent` returns **400** with an explanation
- Consent alone enables nothing
- `biometrics.consent` and `biometrics.enabled` both reach the audit log with the caller's role
- Refusal beats silent disable: an operator must never be wrong about what is running
