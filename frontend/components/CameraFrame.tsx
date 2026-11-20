"use client";

import { useEffect, useState } from "react";
import { fetchFrameBlob } from "@/lib/api";

// How often to ask for a new frame. The pipeline publishes several frames a second, so
// polling every two seconds is what made movement look like a slideshow.
const FRAME_MS = 250;

function healthTone(health: string): "ok" | "warn" | "danger" | undefined {
  const h = (health || "").toLowerCase();
  if (/error|fail|down|stall|dead|offline|disconnect/.test(h)) return "danger";
  if (/ok|live|healthy|running|active/.test(h)) return "ok";
  if (/stop|unknown|warm|start|init|idle|wait|pending/.test(h)) return "warn";
  return undefined;
}

export default function CameraFrame({
  sourceId,
  name,
  health,
}: {
  sourceId: string;
  name: string;
  health: string;
}) {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let handle: ReturnType<typeof setTimeout> | null = null;

    async function poll() {
      const started = Date.now();
      try {
        const blob = await fetchFrameBlob(sourceId);
        if (cancelled) return;
        setUrl((prev) => {
          if (prev) URL.revokeObjectURL(prev);
          return URL.createObjectURL(blob);
        });
      } catch {
        // frame may be unavailable (camera stopped) - keep the last frame
      }
      if (cancelled) return;
      // Scheduled from completion, not from the start: on a slow link an interval would
      // queue requests faster than they complete and the picture would fall behind.
      handle = setTimeout(poll, Math.max(0, FRAME_MS - (Date.now() - started)));
    }

    poll();
    return () => {
      cancelled = true;
      if (handle) clearTimeout(handle);
      setUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return null;
      });
    };
  }, [sourceId]);

  return (
    <div className="card">
      <div className="cam-head">
        <strong>{name}</strong>
        <span className={"badge " + (healthTone(health) ?? "")}>{health || "unknown"}</span>
      </div>
      {url ? (
        <img src={url} alt={name} className="cam-frame" />
      ) : (
        <div className="cam-frame placeholder">No frame yet</div>
      )}
    </div>
  );
}
