/**
 * Describes the SmartCam configuration as labelled, sectioned controls so the
 * Settings screen can be a real UI instead of a JSON blob.
 *
 * Each field maps to a dot-path inside the config object returned by /api/config.
 */
export type Kind = "bool" | "number" | "text" | "secret" | "select" | "tags";

export interface Field {
  path: string;
  label: string;
  kind: Kind;
  help?: string;
  options?: string[];
  step?: number;
  min?: number;
  max?: number;
}

export interface Block {
  title: string;
  note?: string;
  fields: Field[];
}

export interface Section {
  id: string;
  label: string;
  blurb?: string;
  blocks: Block[];
}

export const SECTIONS: Section[] = [
  {
    id: "detection",
    label: "Detection",
    blurb: "How SmartCam looks at each frame and decides something is there.",
    blocks: [
      {
        title: "Model",
        fields: [
          { path: "detection.model", label: "Detection model", kind: "text", help: "File name of the YOLO model, e.g. yolov8n.onnx" },
          { path: "detection.device", label: "Compute device", kind: "select", options: ["cpu", "cuda", "mps"], help: "Use cpu unless this server has a GPU" },
          { path: "detection.imgsz", label: "Inference size", kind: "number", min: 320, max: 1280, step: 32, help: "Larger catches smaller objects but is slower" },
          { path: "workers", label: "Background workers", kind: "number", min: 1, max: 16, help: "Threads for summaries and notifications" },
        ],
      },
      {
        title: "Sensitivity",
        fields: [
          { path: "detection.conf", label: "Confidence threshold", kind: "number", min: 0, max: 1, step: 0.05, help: "Lower = more detections, more false alarms" },
          { path: "detection.iou", label: "Overlap (IoU)", kind: "number", min: 0, max: 1, step: 0.05, help: "How much two boxes may overlap before one is dropped" },
          { path: "detection.frame_stride", label: "Analyse every Nth frame", kind: "number", min: 1, max: 10, step: 1, help: "2 halves the work with little loss of accuracy" },
        ],
      },
      {
        title: "Motion pre-filter",
        note: "Skips frames with nothing moving, which saves a lot of CPU.",
        fields: [
          { path: "detection.motion_enabled", label: "Enable motion pre-filter", kind: "bool" },
          { path: "detection.motion_threshold", label: "Motion sensitivity", kind: "number", min: 0, max: 0.1, step: 0.001, help: "Lower = more sensitive" },
        ],
      },
      {
        title: "Classes to detect",
        note: "Leave empty to detect everything the model knows.",
        fields: [
          { path: "detection.classes", label: "Only these classes", kind: "tags", help: "Comma separated, e.g. person, car, truck" },
        ],
      },
    ],
  },
  {
    id: "alerts",
    label: "Alerts & clips",
    blurb: "What becomes an alert, and how much video is saved around it.",
    blocks: [
      {
        title: "Triggers",
        fields: [
          { path: "events.trigger_classes", label: "Objects that raise events", kind: "tags", help: "Comma separated, e.g. person, car, motorcycle" },
          { path: "events.min_presence_sec", label: "Minimum presence (seconds)", kind: "number", min: 0, step: 0.5, help: "Ignore anything that appears only briefly" },
          { path: "events.cooldown_sec", label: "Cooldown between events (seconds)", kind: "number", min: 0, step: 1, help: "Stops one person producing fifty events" },
        ],
      },
      {
        title: "Saved clips",
        fields: [
          { path: "events.clip_pre_sec", label: "Seconds before the event", kind: "number", min: 0, step: 0.5 },
          { path: "events.clip_post_sec", label: "Seconds after the event", kind: "number", min: 0, step: 0.5 },
          { path: "events.clip_fps", label: "Clip frame rate", kind: "number", min: 1, max: 30, step: 1 },
          { path: "events.clip_max_width", label: "Maximum clip width (px)", kind: "number", min: 320, step: 80, help: "Smaller files, lower detail" },
        ],
      },
      {
        title: "Escalation",
        fields: [
          { path: "events.escalation_sec", label: "Escalate if unhandled for (seconds)", kind: "number", min: 0, step: 30, help: "0 disables automatic escalation" },
        ],
      },
      {
        title: "Behaviour alerts",
        fields: [
          { path: "events.abandoned_sec", label: "Object left behind for (seconds)", kind: "number", min: 0, step: 5 },
          { path: "events.abandoned_classes", label: "Objects watched for abandonment", kind: "tags" },
          { path: "events.abandoned_owner_radius_px", label: "Owner distance (pixels)", kind: "number", min: 0, step: 10 },
          { path: "events.fall_min_sec", label: "Fall detected for (seconds)", kind: "number", min: 0, step: 0.5 },
          { path: "events.fall_bbox_ratio", label: "Fall width/height ratio", kind: "number", min: 0, step: 0.05, help: "A person lying down is wider than tall" },
          { path: "events.fall_angle_deg", label: "Fall angle (degrees)", kind: "number", min: 0, max: 90, step: 1 },
          { path: "events.fall_pose_model", label: "Pose model file", kind: "text" },
        ],
      },
    ],
  },
  {
    id: "live",
    label: "Live video",
    blurb: "How the live view gets video from a camera to a browser.",
    blocks: [
      {
        title: "WebRTC",
        fields: [
          { path: "webrtc.enabled", label: "Enable realtime (WebRTC) view", kind: "bool" },
          { path: "webrtc.stun_urls", label: "STUN servers", kind: "tags", help: "Used to discover the camera's public address" },
        ],
      },
      {
        title: "TURN relay",
        note: "Only needed when a camera sits behind a strict firewall or symmetric NAT.",
        fields: [
          { path: "webrtc.turn_url", label: "TURN server URL", kind: "text", help: "e.g. turn:turn.example.com:3478" },
          { path: "webrtc.turn_username", label: "TURN username", kind: "text" },
          { path: "webrtc.turn_credential", label: "TURN password", kind: "secret" },
        ],
      },
    ],
  },
  {
    id: "storage",
    label: "Storage & privacy",
    blurb: "Where recordings live, how long they are kept, and who can see faces.",
    blocks: [
      {
        title: "Retention",
        fields: [
          { path: "retention.retention_days", label: "Keep recordings for (days)", kind: "number", min: 1, max: 3650, step: 1 },
          { path: "retention.purge_interval_sec", label: "Check for old files every (seconds)", kind: "number", min: 60, step: 60 },
        ],
      },
      {
        title: "Where clips are stored",
        fields: [
          { path: "storage.provider", label: "Storage", kind: "select", options: ["local", "s3"], help: "Local keeps files on this server" },
        ],
      },
      {
        title: "S3-compatible storage",
        note: "Only used when storage is set to s3 above.",
        fields: [
          { path: "storage.bucket", label: "Bucket", kind: "text" },
          { path: "storage.endpoint_url", label: "Endpoint URL", kind: "text" },
          { path: "storage.region", label: "Region", kind: "text" },
          { path: "storage.prefix", label: "Path prefix", kind: "text" },
          { path: "storage.access_key", label: "Access key", kind: "secret" },
          { path: "storage.secret_key", label: "Secret key", kind: "secret" },
        ],
      },
      {
        title: "Privacy",
        fields: [
          { path: "privacy.blur_enabled", label: "Blur people in saved clips", kind: "bool" },
          { path: "privacy.blur_mode", label: "What to blur", kind: "select", options: ["face", "all"] },
          { path: "privacy.encrypt_files", label: "Encrypt files at rest", kind: "bool" },
        ],
      },
    ],
  },
  {
    id: "notify",
    label: "Notifications",
    blurb: "How SmartCam tells somebody that something happened.",
    blocks: [
      {
        title: "Webhook",
        fields: [
          { path: "webhook.enabled", label: "Send events to a webhook", kind: "bool" },
          { path: "webhook.url", label: "Webhook URL", kind: "text" },
          { path: "webhook.timeout_sec", label: "Timeout (seconds)", kind: "number", min: 1, step: 1 },
        ],
      },
      {
        title: "Push notifications",
        fields: [
          { path: "notify.enabled", label: "Enable notifications", kind: "bool" },
          { path: "notify.ntfy_server", label: "ntfy server", kind: "text" },
          { path: "notify.ntfy_topic", label: "ntfy topic", kind: "text" },
          { path: "notify.ntfy_public_key", label: "ntfy public key", kind: "secret" },
          { path: "notify.apprise_url", label: "Apprise URL", kind: "secret", help: "For email, SMS, Telegram and 90+ other services" },
          { path: "notify.e2e_encrypt", label: "Encrypt notifications end to end", kind: "bool" },
        ],
      },
      {
        title: "Scheduled reports",
        fields: [
          { path: "report.enabled", label: "Send a report", kind: "bool" },
          { path: "report.interval", label: "How often", kind: "select", options: ["daily", "weekly"] },
          { path: "report.hour", label: "At which hour (0-23)", kind: "number", min: 0, max: 23, step: 1 },
          { path: "report.notify", label: "Also send a notification", kind: "bool" },
        ],
      },
    ],
  },
  {
    id: "recognition",
    label: "Recognition",
    blurb: "Optional extras: number plates, faces, person tracking and AI summaries.",
    blocks: [
      {
        title: "Number plates (ANPR)",
        fields: [
          { path: "alpr.enabled", label: "Read number plates", kind: "bool" },
          { path: "alpr.min_conf", label: "Minimum confidence", kind: "number", min: 0, max: 1, step: 0.05 },
          { path: "alpr.throttle_sec", label: "Minimum gap between reads (seconds)", kind: "number", min: 0, step: 0.5 },
          { path: "alpr.languages", label: "Plate languages", kind: "text", help: "e.g. en" },
          { path: "alpr.plate_model", label: "Plate model file", kind: "text" },
          { path: "alpr.zones_only", label: "Only inside defined zones", kind: "bool" },
          { path: "alpr.save_crop", label: "Save a picture of each plate", kind: "bool" },
        ],
      },
      {
        title: "Faces",
        fields: [
          { path: "face.enabled", label: "Recognise faces", kind: "bool" },
          { path: "face.model_name", label: "Recognition model", kind: "text" },
          { path: "face.detector_backend", label: "Face detector", kind: "select", options: ["yolov8", "retinaface", "mtcnn", "opencv", "ssd"] },
          { path: "face.min_conf", label: "Minimum confidence", kind: "number", min: 0, max: 1, step: 0.05 },
          { path: "face.throttle_sec", label: "Minimum gap between matches (seconds)", kind: "number", min: 0, step: 0.5 },
          { path: "face.save_crop", label: "Save a picture of each face", kind: "bool" },
        ],
      },
      {
        title: "Person tracking (ReID)",
        fields: [
          { path: "reid.enabled", label: "Track people across cameras", kind: "bool" },
          { path: "reid.model_name", label: "Model", kind: "text" },
          { path: "reid.min_conf", label: "Minimum confidence", kind: "number", min: 0, max: 1, step: 0.05 },
          { path: "reid.throttle_sec", label: "Minimum gap between sightings (seconds)", kind: "number", min: 0, step: 0.5 },
          { path: "reid.save_crop", label: "Save a picture of each sighting", kind: "bool" },
        ],
      },
      {
        title: "AI descriptions",
        note: "Uses a vision model to write a sentence describing each event.",
        fields: [
          { path: "vlm.enabled", label: "Write descriptions", kind: "bool" },
          { path: "vlm.provider", label: "Provider", kind: "text" },
          { path: "vlm.base_url", label: "API base URL", kind: "text" },
          { path: "vlm.model", label: "Model name", kind: "text" },
          { path: "vlm.api_key", label: "API key", kind: "secret" },
          { path: "vlm.max_keyframes", label: "Frames sent per event", kind: "number", min: 1, max: 10, step: 1 },
          { path: "vlm.timeout_sec", label: "Timeout (seconds)", kind: "number", min: 5, step: 5 },
        ],
      },
    ],
  },
];

export function getPath(obj: unknown, path: string): unknown {
  return path.split(".").reduce<unknown>((acc, key) => {
    if (acc && typeof acc === "object") return (acc as Record<string, unknown>)[key];
    return undefined;
  }, obj);
}

/** Immutably set a dot-path, cloning only the objects along the way. */
export function setPath<T>(obj: T, path: string, value: unknown): T {
  const keys = path.split(".");
  const clone: Record<string, unknown> = { ...(obj as Record<string, unknown>) };
  let cur: Record<string, unknown> = clone;
  for (let i = 0; i < keys.length - 1; i++) {
    const key = keys[i];
    const next = cur[key];
    cur[key] = Array.isArray(next) ? [...next] : { ...(next as Record<string, unknown> | undefined) };
    cur = cur[key] as Record<string, unknown>;
  }
  cur[keys[keys.length - 1]] = value;
  return clone as T;
}
