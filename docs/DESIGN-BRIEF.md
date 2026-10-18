# Design Brief — SmartCam

**Status:** Draft 1 · **Date:** 2026-10-17
Describes the design system as implemented in `frontend/app/globals.css` and the component
inventory in `frontend/components/`.

---

## 1. Positioning

SmartCam is **operations software**, not a consumer gadget. It is used by someone mid-incident,
often on a laptop at a front desk, sometimes on a phone in a corridor. Every design decision
follows from that: information density over decoration, status over flourish, speed over polish
that costs a click.

The product's promise is "tell me what happened." The interface should answer that in one
glance before it offers anything to configure.

## 2. Audience and tone

| Segment | Context of use | Tone implication |
|---|---|---|
| Hotels (Nigeria) | Fast-moving, intermittent connectivity, minimal training | Obvious labels, forgiving loading states, no jargon |
| Gated estates (Nigeria) | Estate manager reporting to a residents' association; incidents get forwarded | Calm and factual. The clip is evidence, so the framing must survive being forwarded |

Copy voice: plain, specific, unhurried. Say "2 people detected at Front Gate" — not "AI analysis
complete". Errors say what happened and what to do next. Never blame the user.

## 3. Visual language

**Dark-first.** `color-scheme: dark` is set globally; the palette is tuned for a dim control room
and for long sessions.

### Colour tokens

| Token | Value | Use |
|---|---|---|
| `--bg` | `#0b0e14` | Page background |
| `--surface` | `#131720` | Cards, panels, sidebar |
| `--surface-2` | `#0f131b` | Nested wells, inputs |
| `--surface-hover` | `#1a1f2b` | Hover state |
| `--border` | `#232936` | Default dividers |
| `--border-strong` | `#2f3746` | Emphasised edges |
| `--text` | `#e7eaf0` | Body copy |
| `--text-muted` | `#939cad` | Secondary labels |
| `--text-dim` | `#6b7486` | Tertiary, disabled |
| `--brand` | `#3b82f6` | Primary action, links |
| `--brand-hover` | `#2f6fdd` | Primary hover |
| `--brand-soft` | `rgba(59,130,246,.14)` | Selected row, soft fill |
| `--ok` | `#22c55e` | Resolved, healthy |
| `--warn` | `#f59e0b` | Pending, degraded |
| `--danger` | `#ef4444` | Escalated, destructive |
| `--danger-soft` | `rgba(239,68,68,.13)` | Destructive hover fill |

**Rule:** status colour is semantic and never decorative. Green means resolved or healthy — never
"nice accent". A red badge always means attention is required.

### Shape and space

| Token | Value |
|---|---|
| `--r-sm` | 8px |
| `--r` | 12px |
| `--r-lg` | 16px |
| `--shadow` | `0 1px 2px rgba(0,0,0,.5)` |
| `--sidebar-w` | 236px |
| `--topbar-h` | 58px |

Content is capped at **1280px** and centred, with 1.5rem padding. Depth is expressed by surface
tint and 1px borders, not by heavy shadows.

### Type

System font stack: `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`. No web font — it
costs a request and buys nothing on an operations dashboard.

| Level | Size | Treatment |
|---|---|---|
| h1 | 1.45rem | Tight tracking (`-.015em`) — page title |
| h2 | 1.02rem | Section heading, generous top margin |
| h3 | .98rem | Card title |
| Body | 1rem | — |
| Sub / muted | .92rem | `--text-muted` |

## 4. Layout shell

Persistent left sidebar (236px) and top bar (58px). The shell is `components/AppShell.tsx`.

- **Sidebar** — product mark, primary navigation, current-item highlight using `--brand-soft`.
- **Top bar** — page context, connection state, account.
- **Content** — `main`, max 1280px.
- **Co-pilot drawer** — overlays from the right; never displaces the working area.

Auth pages (`/login`, `/register`, `/invite/:token`) sit outside the shell, centred, single column.

## 5. Component inventory

| Component | Purpose |
|---|---|
| `AppShell` | Sidebar + top bar + content frame |
| `PageHead` | Title, subtitle, page-level actions |
| `EmptyState` | What this page is for and how to start |
| `Badge` | Status pill; `confTone()` maps confidence to colour |
| `Icon` | Inline SVG set, no icon-font dependency |
| `SettingsFields` / `Control` | Schema-driven form controls for settings |
| `ZoneEditor` | Draw and adjust detection zones over a frame |
| `EventThumb` | Thumbnail with lazy load and fallback |
| `CameraFrame` / `LiveFeed` | MJPEG display and connection state |
| `WebRTCLiveFeed` | WebRTC video with ICE handling |
| `ClipPlayer` | Event clip playback |
| `Copilot` | Vera chat drawer |

**Settings is schema-driven.** `lib/settings-schema.ts` defines `SECTIONS` and `ZONE_FIELDS`; the
page renders controls from that definition. Adding a setting means adding a field to the schema —
not editing a page. Preserve this: it is why the raw-JSON tab could be removed safely.

## 6. Interaction patterns

- **Triage first.** Alerts are actionable from the list — ack, resolve, assign, escalate — without
  opening a detail page.
- **Progressive disclosure.** Advanced configuration lives in tabs, not one long form. The raw JSON
  editor was removed deliberately: it exposed implementation detail to operators.
- **Optimistic feedback for triage.** Acknowledging should feel instant; reconcile after.
- **Never a dead end.** Every empty state explains the next action.
- **Status is always visible.** Connection state for live video is shown, not inferred from a
  frozen frame.
- **Confidence is shown honestly.** Detection confidence is rendered as a tone-mapped badge, not a
  binary "match".

## 7. Accessibility requirements

Current gaps are real and should be treated as work, not as done:

- **Contrast** — `--text-dim` on `--surface` is below WCAG AA for body text. Use it for
  non-essential metadata only, or lighten it.
- **Focus** — focus styles must be visible on every interactive element; dark themes routinely lose
  them. Verify keyboard traversal of the shell and the settings tabs.
- **Colour is not the only signal** — status badges carry text labels as well as colour. Keep it
  that way.
- **Motion** — respect `prefers-reduced-motion` for the drawer and any transitions.
- **Video** — live view has no captions or text alternative; the event summary is the accessible
  substitute and should always be present.

## 8. Marketing site direction

**The pages currently in `frontend/app/(site)/` do not belong to this product.** They are written
for a Canadian long-term-care company — for-nursing-homes, for-families, a wandering and elopement
checklist, PIPEDA compliance page. They should be moved to that project's own repository.

This product needs its own marketing site for **hotels and gated estates**. Direction: lead with
the incident, not the technology. "At 2:14am someone was at the east gate for four minutes. Here
is the clip." The buyer is a hotel manager or estate manager who answers to an owner or a
residents' association, and who is judged on how quickly and clearly they can explain what
happened.

Tone: plain and operational, not reassuring and not macho. Avoid surveillance language — estate
residents are also the audience for the output, and "we watch your perimeter" reads worse than
"you can show what happened."

## 9. Deliverables expected from a designer

1. A component sheet proving every `--*` token has a documented use.
2. Empty, loading and error states for each of the eleven authenticated pages.
3. Mobile layouts for dashboard, alerts and live view — currently desktop-first.
4. An accessibility pass fixing §7, with contrast checked against the real tokens.
5. Marketing site art direction, aligned to whichever segment is chosen.
