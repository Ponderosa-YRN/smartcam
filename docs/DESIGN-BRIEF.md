# Design Brief — SmartCam
**Version 2.0 · reflects commit `f6b27ea`**

---

## 1. Positioning

Operations software for a hotel or estate, used mid-incident by someone who is not a technologist.
Density over decoration, status over flourish. The interface should answer "what happened" before it
offers anything to configure.

## 2. Audience

| Segment | Context | Tone |
|---|---|---|
| Hotels (Nigeria) | Front desk, duty manager, intermittent power and connectivity | Obvious labels, forgiving loading states, no jargon |
| Gated estates | Estate manager reporting to a residents' association; incidents get forwarded | Calm and factual — the clip is evidence and must survive being forwarded |

Copy voice: plain, specific, unhurried. "2 people at the east gate", not "AI analysis complete".
Errors say what happened and what to do next. Never blame the user.

---

## 3. Visual language

Dark-first (`color-scheme: dark`). Depth by surface tint and 1px borders, not shadow.

| Token | Value | Use |
|---|---|---|
| `--bg` | `#0b0e14` | Page |
| `--surface` | `#131720` | Cards, panels, sidebar |
| `--surface-2` | `#0f131b` | Inputs, nested wells |
| `--border` | `#232936` | Dividers |
| `--text` | `#e7eaf0` | Body |
| `--text-muted` | `#939cad` | Secondary |
| `--brand` | `#3b82f6` | Primary action |
| `--ok` / `--warn` / `--danger` | `#22c55e` / `#f59e0b` / `#ef4444` | Status |

**Status colour is semantic, never decorative.** Green is resolved or healthy. Red always means
attention is required.

Shape: `--r-sm` 8px, `--r` 12px, `--r-lg` 16px. Shell: sidebar 236px, topbar 58px, content capped
at 1280px. Type: system stack, h1 1.45rem, h2 1.02rem, body 1rem, muted .92rem.

---

## 4. Shell and pages

Sidebar + top bar (`AppShell`), content area, co-pilot drawer overlaying from the right. Auth pages
sit outside the shell.

| Page | Purpose |
|---|---|
| `/dashboard` | Four metrics — cameras online, open alerts, **people on site**, **vehicles on site** — plus camera grid and recent activity |
| `/live` | Snapshot (2 s frames) or Realtime (WebRTC) |
| `/alerts` | Triage queue: ack, resolve, assign, escalate |
| `/events` | Chronological list with filters; **Report** button per row |
| `/search` | Query over events |
| `/plates`, `/faces`, `/track` | Recognition surfaces |
| `/analytics` | Occupancy history, heatmap, counts |
| `/import` | Upload a recording for one-off analysis |
| `/admin` | Tenants, users, devices, invites, billing |
| `/settings` | Cameras, Zones, Detection, Alerts & clips, Live video, Storage & privacy, Notifications, Recognition |

`/` is a landing page for anyone signed out and redirects signed-in users to the dashboard.

---

## 5. Components

`AppShell` · `PageHead` · `EmptyState` · `Badge` (+ `confTone`) · `Icon` · `SettingsFields`/`Control` ·
`ZoneEditor` · `EventThumb` · `CameraFrame` · `LiveFeed` · `WebRTCLiveFeed` · `ClipPlayer` · `Copilot`

**Settings is schema-driven.** `lib/settings-schema.ts` defines sections and fields; the page renders
controls from that definition. Adding a setting is a schema entry, not page surgery — the reason the
raw-JSON tab could be removed safely.

---

## 6. Interaction patterns

- **Triage first.** Alerts act from the list — no detail page required
- **Progressive disclosure.** Advanced configuration lives in tabs
- **Never a dead end.** Every empty state names the next action
- **Connection state is visible**, not inferred from a frozen frame
- **Confidence is honest.** Rendered as a tone-mapped badge, not "match"
- **Destructive actions are explicit.** Biometric enablement is refused rather than silently reverted

---

## 7. Accessibility gaps

- `--text-dim` on `--surface` fails AA for body text — metadata only
- Focus styles must be checked across the shell and settings tabs
- Status badges carry text as well as colour — keep it that way
- Respect `prefers-reduced-motion` for the drawer
- Live view has no text alternative; the event summary is the accessible substitute

---

## 8. What the product should look like next

| Priority | Why |
|---|---|
| **PDF report styling** | It leaves the product and lands in front of police, insurers and an association. It is currently plain by design — this is the one artefact to make look deliberate |
| Four-metric dashboard reads left-to-right | People and vehicles now sit together; keep the pair adjacent |
| Camera-offline banner | A frozen frame and a working one look identical; the badge is a small signal for a large trust problem |
| Mobile triage | A duty manager triages from a phone, not a desk |
