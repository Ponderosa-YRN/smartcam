# Implementation Plan — SmartCam

**Status:** Draft 1 · **Date:** 2026-10-17
**Companion documents:** `docs/PRD.md`, `docs/TECHNICAL-REQUIREMENTS.md`, `docs/BACKEND-SCHEMA.md`

---

## 1. Where the project actually is

| Area | State |
|---|---|
| Core product | Works end to end: detection, events, triage, search, recognition, live video |
| Multi-tenant security | Hardened this session; the high-severity gaps are closed |
| Deployment | Docker on one VPS, Caddy single origin, deploy scripts that survive failure |
| Site availability | **Deliberately dark** — firewall drops everything but SSH, verified externally |
| Security audit | **Incomplete** — the mandated validators cannot run on Windows; needs a POSIX host |
| Billing | Data model only; no payment path |
| Marketing site | Half-built, untracked, no backup, and aimed at a different segment than the product |
| Segment choice | **Undecided** — hospitality vs long-term care |

**The single most important fact:** the product is further along than the business decision behind
it. The next phase should be gated on deciding who it is for, because that choice changes privacy
defaults, consent requirements, pricing and the entire marketing site.

## 2. Workstreams

| # | Workstream | Blocks |
|---|---|---|
| W1 | Decide the segment | Everything commercial |
| W2 | Finish security | Public launch |
| W3 | Deploy and verify | Anything customer-facing |
| W4 | Back up irreplaceable work | Nothing — do it now |
| W5 | Product gaps | Demo credibility |
| W6 | Payment and plans | Revenue |
| W7 | Operability | Running paying customers |

## 3. Phase 0 — stop the bleeding (today, ~1 hour)

| Task | Why | Effort |
|---|---|---|
| Commit and push the marketing site | It exists only on one disk. Everything else here is recoverable; this is not | 10 min |
| Confirm firewall rules are persisted | `grep -c 'INPUT -j DROP' /etc/iptables/rules.{v4,v6}` → both 1 | 5 min |
| Deploy `e86f64b` (billing, uploads, audit, WS token) | Committed but not running | 20 min |
| Remove the stale `smartcam-old` container | Keeps the deploy script re-runnable | 2 min |

**Exit criteria:** a reboot does not republish the site, and nothing of value exists on exactly one
machine.

## 4. Phase 1 — decide the market (1 week, no code)

Not an engineering phase. Its output is one paragraph that says which segment is first.

- Talk to five prospects in the chosen segment. One question: *what did you do the last time
  something happened on camera?*
- Establish whether face recognition is lawful in the target setting. For Canadian long-term care
  this is a **hard gate** — if consent cannot be obtained, the biometric features are not sellable
  there and the product must adapt (re-ID of residents may be permitted where face recognition
  is not).
- Price against what they pay today, not against software.

**Exit criteria:** a named segment, a named first customer type, and a documented answer on
biometrics legality.

**If this phase is skipped, Phase 5 is wasted effort.**

## 5. Phase 2 — close the security backlog (3–5 days)

Ordered by risk. All are small.

| # | Item | Where | Effort |
|---|---|---|---|
| 2.1 | Restrict CORS to the real origin; it currently defaults to `*` | `api.py:61` | 1 h |
| 2.2 | Cap concurrent `/api/stream` viewers | `api.py:672-696` | 2 h |
| 2.3 | Thread the caller's tenant through every write path | `db.py:695-915` | 4 h |
| 2.4 | Make `privacy.encrypt_files` either work or disappear | `config.py`, `crypto.py` | 4 h or 30 min |
| 2.5 | Harden the co-pilot against device-controlled text | `frontend/lib/copilot.ts` | 3 h |
| 2.6 | Add route-level authorization tests | `tests/` | 1 day |

**On 2.4:** the lazy and honest option is to delete the toggle and say media is not encrypted at
rest. A switch that does nothing is worse than no switch, because it creates false confidence in a
sales conversation.

**On 2.6:** today no test would fail if the tenant checks were removed. That is the difference
between "fixed" and "stays fixed".

**Exit criteria:** every row above closed, and a test that fails if a tenant check is deleted.

## 6. Phase 3 — operate it properly (2–3 days)

| Task | Detail |
|---|---|
| Run the security audit on the VPS | The validators need POSIX; they refuse to run on Windows. This is the only way to reach a certified result |
| Off-site backups | Nightly `data/` archive (database, config, clips, audit log) to object storage, with a **tested** restore |
| Uptime and disk alerting | Disk-full is the most likely way this product dies quietly |
| Document the restore procedure | Written down and rehearsed once, not imagined |
| Add `events(tenant_id, start_ts)` index | Every list query needs it once there are real tenants |

**Exit criteria:** a rehearsed restore from backup, and an alert that fires before disk exhaustion.

## 7. Phase 4 — make the demo undeniable (1–2 weeks)

The product works; the demo is the bottleneck for a 20-customer target.

| Task | Why |
|---|---|
| Seed a realistic site: 3 cameras, 24 h of events, known faces, plates | An empty dashboard sells nothing |
| One-page PDF per incident: event, clip, timeline, summary | This is what a manager forwards to their boss |
| Onboarding checklist: camera → zone → alert rule → phone | Time-to-first-alert is the metric |
| Mobile triage view | A manager triages from a phone, not a desk |
| Remove or hide the legacy Streamlit app | Two dashboards confuse a buyer and the old one is not tenant-scoped |

**Exit criteria:** a stranger can go from cold to "I understand what this does" in five minutes,
unassisted.

## 8. Phase 5 — revenue path (1–2 weeks)

| Task | Detail |
|---|---|
| Stripe: customers, subscriptions, webhook | `stripe_customer_id` and `stripe_subscription_id` already exist |
| Enforce plan limits | `max_cameras` is defined but not enforced at camera creation |
| Trial → paid flow | With a real expiry |
| Receipts and dunning | Non-optional once money moves |

**Exit criteria:** a customer can pay without you touching anything, and limits actually bind.

## 9. Phase 6 — relaunch (3 days)

| Task | Detail |
|---|---|
| Rebuild and deploy the web tier | `deploy_web.sh` — blocked on the marketing site being finished |
| Ship the frontend half of the WebSocket token change | Server already accepts both forms |
| Remove the firewall drop for 80/443 | Keep SSH restricted |
| Verify from outside | Login, live video, an event, a clip, a co-pilot answer |
| Watch for 72 hours | Errors, latency, disk |

**Exit criteria:** an external user completes the full loop unaided.

## 10. Sequencing summary

```
Phase 0  today        ← do not skip; one hour buys back irreplaceable work
Phase 1  week 1       ← decision, not code. Gates everything commercial
Phase 2  week 1-2     ← security backlog
Phase 3  week 2       ← backups, alerting, certified audit
Phase 4  week 3-4     ← demo quality
Phase 5  week 4-5     ← payments
Phase 6  week 5-6     ← relaunch
```

Two months to twenty customers is achievable **only if Phase 1 does not slip**. Engineering is not
the constraint; the market decision is.

## 11. Risks to this plan

| Risk | Mitigation |
|---|---|
| Phase 1 skipped, work built for nobody | Treat it as a hard gate with a dated decision |
| Biometrics prohibited in the target market | Confirm in Phase 1, before building consent flows |
| Single VPS fails | Phase 3 backups; accept a documented RTO |
| Security regression after the audit | Phase 2.6 tests |
| Founder is the only executor | Ruthless sequencing; nothing runs in parallel |
| The marketing site is lost | Phase 0, today |

## 12. What is explicitly not in this plan

- Multi-region or high availability
- On-premise packaging and licensing
- Mobile native apps
- Additional detection models beyond the current set
- Postgres migration (available, untested, not needed at this scale)

Each is a real option later. None of them moves a customer this quarter.
