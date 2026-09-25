# SmartCam — Client Presentation Script
## 2-minute intro + 5-minute live demo + Q&A

---

## 0. Before you present (do this first)

1. Start both servers (see docs/APP_OVERVIEW.md section 7).
2. Log in as **admin** and click through every tab once so nothing loads blank.
3. **Pre-populate data:** import a video 1–2 times before the meeting so the
   Events, Alerts, and Clips pages already have content to show.
4. Have a short video ready for the live demo (demo/demo.avi works great — it
   has pedestrians).
5. Keep a **backup** ready: if a live camera won't start, fall back to the
   Import demo (it always works).
6. Optional but powerful: if you configure an OpenAI key, event clips get
   **AI-written summaries** — a strong "wow" moment.

---

## PART 1 — The intro (2 minutes)

*(Smile, one breath, then:)*

**Open (30s)**
> "Good [morning/afternoon]. SmartCam does one thing really well: it gives your
> existing security cameras a brain. Instead of cameras that just record and
> wait for something bad to happen, SmartCam watches the video in real time,
> understands what it's seeing, and tells your staff the moment something needs
> attention."

**The problem (30s)**
> "Today, most hotels have dozens of cameras recording hours of footage that
> nobody watches. When an incident happens, someone has to scrub through hours
> of video to find it — often too late. We fix that."

**The promise (45s)**
> "SmartCam detects people and vehicles in real time. It raises instant alerts
> for the things that matter in a hotel — someone loitering where they
> shouldn't, a restricted door being entered, a crowd forming, a guest falling,
> or a bag left unattended. It records a short clip of every event, sends an
> alert to your phone, and lets you search the footage by what happened — type
> 'person at night' and find it in seconds."

**The hook (15s)**
> "And it does all of this on the cameras you already have. Let me show you."

*(Transition into the demo.)*

---

## PART 2 — The live demo (5 minutes)

### Step 1 — Live view (60s)
**Click:** Live tab.
**Say:**
> "This is the live view. Every camera is running our AI in real time. Watch the
> boxes — each one is a person or vehicle the system has detected and is
> tracking. The number stays with them as they move, so we know it's the same
> person from frame to frame."
**Point out:** the boxes, the camera health status, the multi-camera grid.

### Step 2 — Import a video live (90s)
**Click:** Import tab → choose your video → (leave "Fast processing" unchecked
so it plays at real speed) → "Import & analyze".
**Say:**
> "This is my favorite part. I'm going to feed it a video it has never seen.
> Watch it analyze the footage live — detecting, tracking, and drawing boxes as
> it goes, while the counters update in real time."
**Point out:** the live frame, the frames/FPS/objects counters, and — when it
finishes — the list of events it found.

### Step 3 — Events & clips (60s)
**Click:** Events tab → open a recent event → "Play clip".
**Say:**
> "Every event is automatically clipped, with a few seconds before and after so
> you never miss context. This is what your staff would open right after an
> alert."
*(If summaries are configured:)*
> "And the AI has already written a summary of what happened in plain English."

### Step 4 — Smart search (45s)
**Click:** Search tab → type "person at night" → Search.
**Say:**
> "This is the killer feature for investigations. No more scrubbing. You search
> by what happened — 'car yesterday', 'person near the pool' — and get the
> matching clips instantly."

### Step 5 — Analytics (45s)
**Click:** Analytics tab.
**Say:**
> "And for the operations team, it counts people and vehicles in real time,
> shows foot-traffic heatmaps, and produces daily or weekly incident reports.
> Great for staffing and security planning."

### Step 6 — Admin & multi-site (45s, if time)
**Click:** Admin tab.
**Say:**
> "Finally, the multi-site story. Every hotel is its own isolated tenant, with
> its own cameras, users, and roles — manager, security, front desk — each
> seeing only what they're allowed to. One platform, all your properties."

---

## PART 3 — Anticipated questions & answers

**Q: Do we need to replace our cameras?**
> No. It works with existing IP/RTSP cameras (and even webcams or video files).

**Q: Is this cloud or on-site?**
> Either. We recommend a small on-site box per hotel for the AI (cameras stay
> local, lowest latency, best privacy), with a cloud dashboard to manage all
> your properties from anywhere.

**Q: How accurate is it?**
> Very good for common objects — people, vehicles, bags. It's built on YOLOv8,
> a leading open model, and we can tune it per site if needed.

**Q: Does it need an expensive GPU?**
> No. It's optimized to run on ordinary CPUs (we use ONNX, and OpenVINO on Intel
> for a further boost). A GPU is optional for very large deployments.

**Q: What about privacy / GDPR?**
> Privacy is built in: we can blur faces in live view and recordings, face data
> requires consent, you can delete a person's data in one click, and alerts can
> be end-to-end encrypted.

**Q: Can it read number plates?**
> Yes — automatic plate recognition for gate/parking management.

**Q: Can it follow someone across cameras?**
> Yes — our person re-identification tracks the same individual as they move
> between cameras.

**Q: What does it cost to run?**
> Very low — a modest server can handle a site, with no per-camera licensing.

**Q: Can we try it?**
> Absolutely — we can set up a pilot on a few of your cameras. (This is your
> close — suggest a concrete next step.)

---

## PART 4 — The close (30s)

> "So in short: SmartCam makes your existing cameras proactive. It detects the
> events that matter, alerts your team instantly, and makes every second of
> footage searchable. I'd love to run a pilot on a few of your cameras — when
> would be a good time to scope that?"

---

## Quick pro tips

- **Practice the Import demo once** — it's the most visually impressive part.
- **Don't over-promise** the recognition features (faces, plates, cross-camera)
  unless you've installed their dependencies and tested them live. Detection,
  tracking, events, search, and analytics are rock solid — lead with those.
- **If a live camera fails**, pivot immediately to Import — it never fails.
- **Have the docs open:** docs/APP_OVERVIEW.md for details, docs/ARCHITECTURE.md
  for the "where this goes next" multi-site/cloud story.
