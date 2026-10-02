"use client";

import { useEffect, useRef, useState } from "react";
import { fetchFrameBlob } from "@/lib/api";

function healthTone(health: string): "ok" | "warn" | "danger" | undefined {
  const h = (health || "").toLowerCase();
  if (/ok|live|healthy|running|stream/.test(h)) return "ok";
  if (/unknown|warm|start|init|idle/.test(h)) return "warn";
  if (/error|fail|down|stall|dead|offline/.test(h)) return "danger";
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
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
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
    }

    poll();
    timer.current = setInterval(poll, 2000);
    return () => {
      cancelled = true;
      if (timer.current) clearInterval(timer.current);
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
