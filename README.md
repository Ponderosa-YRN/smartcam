# SmartCam — YOLOv8 Smart Security Camera Platform

SmartCam turns any RTSP camera, webcam, or video file into an intelligent
surveillance system. It combines **YOLOv8** object detection, **ByteTrack**
multi-object tracking, automatic event clips, AI-generated summaries from a
vision-language model, smart search, and mobile notifications — with an
optional end-to-end encrypted notification path.

## Features

- **Real-time detection + tracking** — YOLOv8 (any model: n/s/m/l/x) with ByteTrack.
- **Event clips** — auto-recorded with pre-roll buffer, thumbnails, and metadata.
- **Smart search** — query by object (person, car), time-of-day (night),
  dates (today, yesterday), or free text.
- **AI summaries** — each event is summarized by a pluggable vision-language model
  (any OpenAI-compatible endpoint, or local Ollama).
- **Mobile notifications** — ntfy, Pushover, Telegram, Slack, and dozens more via apprise.
- **End-to-end encryption** — optional ntfy E2E path (NaCl box, experimental).
- **Live dashboard** — Streamlit UI for monitoring, clips, search, and settings.
- **Import video for assessment** — upload a video (Import tab) to analyze it once and generate events/clips.
- **Vehicle plate recognition (ANPR)** — read license plates via EasyOCR (optional), with a searchable plate log and plate on events/notifications.

**Hotel safety & operations**
- Loitering detection, restricted-zone intrusion, queue/crowd alerts
- Fall detection and abandoned-object/baggage detection
- Parking occupancy counting and foot-traffic heatmaps
- Privacy face/body blurring, data retention/auto-purge
- Dashboard login + roles, incident reports, webhook/API delivery

## Architecture

    source (rtsp/file/webcam) --> detector (YOLOv8 + ByteTrack) --> pipeline
                                                                    |
          +----------------------+-----------------+----------------+
          v                      v                 v                v
    SQLite events          clip .mp4 +        VLM summary       apprise /
                          thumbnails.jpg      (background)      ntfy E2E
          |
          v
    Streamlit dashboard (reads events + clips)

## Project layout

    app.py                    Streamlit dashboard entry point
    smartcam/
      config.py               dataclass config + JSON load/save
      detector.py             YOLOv8 + ByteTrack wrapper
      pipeline.py             source -> events -> clips (background thread)
      db.py                   SQLite event store
      search.py               natural-language smart search
      summarize.py            pluggable VLM summarizer
      notify.py               apprise + optional ntfy E2E
      utils.py                helpers (thumbnails, keyframes, drawing)
    scripts/
      run_pipeline.py         headless pipeline runner
      download_demo.py        fetch a small public demo clip
    demo/make_synthetic.py    generate a synthetic test clip
    config.example.json       example configuration

## Requirements

- Python 3.10+ (developed on 3.11)
- Windows / macOS / Linux
- A CPU is enough (a GPU is strongly recommended for real-time speed)

## Install

    python -m venv .venv
    .venv\Scripts\python -m pip install --upgrade pip
    .venv\Scripts\python -m pip install -r requirements.txt

On first run, YOLOv8 downloads its weights (e.g. yolov8n.pt, ~6 MB) automatically.

## Configure

Copy the example and edit it:

    copy config.example.json config.json

Key sections:

- sources — one entry per camera. uri can be 0 (webcam), an RTSP/HTTP URL,
  or a local video path.
- detection — model, image size, confidence/IoU, tracker, frame stride
  (raise frame_stride to lower CPU load).
- events — which objects trigger an event, presence threshold, cooldown,
  and clip length around each event.
- vlm — provider (openai or ollama), base URL, model, and API key.
- notify — apprise URL and optional ntfy E2E settings.
- zones — named polygons with rules (see "Hotel features" below).
- privacy — blur faces or bodies in live view and clips.
- retention — auto-delete clips/records after N days.
- auth — dashboard login with users/roles.
- webhook — POST event JSON to an external URL.
- report — periodic incident summary.

Secrets can also be provided as environment variables instead of writing them to disk:

- SMART_CAM_OPENAI_API_KEY
- SMART_CAM_NOTIFY_URL
- SMART_CAM_NTFY_TOPIC
- SMART_CAM_DATA_DIR

## Run

Dashboard (web UI):

    .venv\Scripts\python -m streamlit run app.py

Headless (detect/record/notify without the UI):

    .venv\Scripts\python scripts\run_pipeline.py --config config.json

**Remote mode (headless API + dashboard as separate processes):**

    # terminal 1 — backend (runs the pipeline, serves the REST API)
    .venv\Scripts\python run_api.py --port 8000

    # terminal 2 — dashboard reading from the API
    set SMART_CAM_API_URL=http://localhost:8000
    .venv\Scripts\python -m streamlit run app.py

## Try it with a demo clip

    .venv\Scripts\python scripts\download_demo.py
    # then set a source uri to demo/demo.avi in config.json, or run:
    .venv\Scripts\python scripts\run_pipeline.py --config config.json

## Hotel features

Define **zones** in config.json as polygons (normalized 0..1 coordinates). Each
zone can carry rules:

- max_occupancy — queue/crowd alert when the number of people reaches it.
- loiter_sec — alert when someone stays in the zone beyond this many seconds.
- restricted + allowed_window — intrusion alert outside the "HH:MM-HH:MM" window.
- parking + capacity — count vehicles and alert when the lot is full.

Example:

    "zones": [
      {
        "id": "lobby", "name": "Lobby",
        "points": [[0.05, 0.05], [0.95, 0.05], [0.95, 0.95], [0.05, 0.95]],
        "classes": ["person"], "max_occupancy": 8, "loiter_sec": 60.0
      },
      {
        "id": "roof", "name": "Roof (staff only)",
        "points": [[0.0, 0.0], [1.0, 0.0], [1.0, 0.5], [0.0, 0.5]],
        "classes": ["person"], "restricted": true, "allowed_window": "06:00-22:00"
      }
    ]

Fall detection uses a body-aspect heuristic; abandoned-object detection watches
static luggage/bags with no owner nearby. These are tuned under the "events"
section (fall_bbox_ratio, fall_min_sec, abandoned_sec, ...).

## Notifications

Notifications use apprise, so any of its services work — set notify.apprise_url
to e.g.:

- ntfy://my-topic  (or ntfys://myhost/my-topic for TLS)
- pushover://user_key:app_token
- tgram://botToken/chatId

### End-to-end encryption (experimental)

Enable notify.e2e_encrypt, set notify.ntfy_topic, and provide the recipient's
base64 X25519 public key in notify.ntfy_public_key. The message is encrypted
with NaCl box before it is published. This path is experimental — verify
compatibility with your ntfy client's key format before relying on it in
production. The default apprise path is already encrypted in transit (HTTPS).

## AI summaries

- OpenAI-compatible (default): set vlm.base_url to any /chat/completions
  endpoint (OpenAI, OpenRouter, vLLM, ...), plus vlm.model and vlm.api_key.
- Ollama (local): set vlm.provider to ollama, vlm.base_url to
  http://localhost:11434, and vlm.model to a vision model such as llava.

Summaries run in the background so they never block detection.

## Production & polish

- Adaptive inference — auto-lowers resolution and frame rate when the scene is
  idle, then returns to full quality on motion.
- File logging — rotating logs under data/smartcam.log.
- Pipeline watchdog — dead pipeline threads are auto-restarted.
- Audit trail — login/logout, start/stop, and config changes are logged to
  data/audit.log.
- Dark theme, multi-camera grid view, event filters (date/camera/type), clip
  download, and a browser alert toast + sound.
- HTTPS — run Streamlit with --server.sslCertFile and --server.sslKeyFile.

## Notes & limitations

- This machine has no GPU, so detection runs on CPU. Use a smaller model
  (yolov8n.pt) and a higher frame_stride for acceptable frame rates.
- The ntfy E2E path and the exact VLM provider behavior depend on your
  endpoints; both are isolated behind small adapters so they are easy to swap.
