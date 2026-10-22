# Implementation Plan — SmartCam
**Version 2.0 · reflects commit `f6b27ea`**

---

## 1. Where the product actually is

| Area | State |
|---|---|
| Core product | Works end to end: detection, events, triage, PDF evidence, search, recognition, live video, co-pilot |
| Multi-tenant security | Hardened; 13 regression tests plus a sweep of all 76 HTTP routes |
| Deployment | One VPS, full pipeline image, Caddy single origin, deploy scripts that survive failure |
| Monitoring | Disk and site-render checks to Telegram. **Nothing external** |
| Backups | Nightly database + weekly media. **No off-site copy** |
| Payment | None. Invoices are manual |
| Customers | **Zero** |
| Compliance | Consent gate built; **DPIA, signage, DSR and Nigerian residency all missing** |

**The gap is commercial, not technical.** No feature on the list below substitutes for one paying customer.

---

## 2. Workstreams

| # | Workstream | Gates |
|---|---|---|
| W1 | Ship the three priority features | Nothing — they are built, just undeployed |
| W2 | Sell one customer | Everything commercial |
| W3 | NDPA paperwork | Any claim of compliance |
| W4 | Off-site backup | Surviving a dead VPS |
| W5 | External monitoring | Hearing about outages from you, not the customer |

---

## 3. Phase 0 — deploy what exists (this week)

| Task | Effort | Why |
|---|---|---|
| Push and deploy `7929219`, `83369e6`, `f6b27ea` | 1 h | The PDF, multi-channel notify and consent gate are built but not live |
| Confirm the image no longer contains streamlit | 5 min | Proves the unscoped UI cannot run |
| Finish the off-site backup (rclone remote) | 30 min | The only unrecoverable risk |
| Ask one hotel for their NVR details | 15 min | Turns tomorrow's visit into a formality |

---

## 4. Phase 1 — first customer (weeks 1–3)

| Task | Effort | Impact |
|---|---|---|
| **WhatsApp or email alerts to a real distribution list** | 2 d | Email already works via apprise; WhatsApp needs a gateway account. Alerts that reach nobody are the product's weakest link |
| **PDF report styling pass** | 1 d | It leaves the product and lands in front of police and insurers |
| **Camera-offline alerting** | 2 d | In Nigeria a power cut is the normal case; today it is silent |
| **Onboard one hotel or estate end to end** | — | The only thing that validates any of this |

**Exit criteria:** one site live, one invoice sent, one incident exported as a PDF by the customer.

---

## 5. Phase 2 — table stakes (weeks 4–8)

| Task | Effort | Impact |
|---|---|---|
| ONVIF discovery | 5 d | 60 hand-typed URLs is your install cost, and it is per deal |
| Low-bandwidth mode (sub-stream default, adaptive fps) | 4 d | Unlocks sites on thin uplinks |
| MFA for admin and manager | 2 d | Removes the most common IT objection |
| NDPA pack v1: DPIA generator + signage templates | 6 d | Trust signal no local competitor has |
| Plan limits actually enforced | 2 d | Limits are defined and ignored |

---

## 6. Phase 3 — differentiators (weeks 9–12)

| Task | Effort | Impact |
|---|---|---|
| Power resilience: edge box recording locally, syncing on recovery | 10 d | The strongest story available in this market |
| Data residency in Nigeria or an African region | 5 d | Required to make compliance claims honestly |
| Access control integration (gate relay or partner) | 10 d | Closes the "half a security product" gap |
| Site-scoped roles for multi-gate estates | 4 d | Enables the group pitch |

---

## 7. Standing backlog (not scheduled)

- WebSocket route tests (both handlers loop forever; needs a receive timeout)
- Certified security audit — must run on the VPS, validators refuse on Windows
- **AGPL-3.0 resolution** on the detector: licence it, or move to an Apache-2.0 model
- External uptime monitoring that can report the box being unreachable
- Daily in/out totals, if a customer asks — needs an entrance line per camera
- Fire/smoke model, if a customer asks — `docs/FIRE-MODEL-PLAN.md`

---

## 8. Sequencing

```
Now      deploy, backup remote, NVR details
Week 1-3 first customer + alerts that reach a phone
Week 4-8 install cost down, bandwidth, MFA, NDPA pack
Week 9-12 power resilience, residency, access control
```

---

## 9. Explicitly not in this plan

Multi-region, high availability, mobile native apps, SOC 2, on-premise packaging, Postgres migration.
Each is a real option later; none moves a customer this quarter.
