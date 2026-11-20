"use client";

import { useEffect, useState } from "react";
import { fetchStreamUrl } from "@/lib/api";

// The stream token is good for ten minutes; refresh before that so a long-open tab does
// not freeze. The existing <img> keeps showing frames while the new URL is fetched.
const REFRESH_MS = 8 * 60 * 1000;

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
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let refresh: ReturnType<typeof setTimeout> | null = null;

    async function mint() {
      try {
        const next = await fetchStreamUrl(sourceId);
        if (cancelled) return;
        setUrl(next);
        refresh = setTimeout(mint, REFRESH_MS);
      } catch {
        if (cancelled) return;
        // Camera stopped, token refused, or the API is down: retry in a moment.
        setUrl(null);
        refresh = setTimeout(mint, 3000);
      }
    }

    mint();
    return () => {
      cancelled = true;
      if (refresh) clearTimeout(refresh);
      setUrl(null);
    };
  }, [sourceId, nonce]);

  return (
    <div className="card">
      <div className="cam-head">
        <strong>{name}</strong>
        <span className={"badge " + (healthTone(health) ?? "")}>{health || "unknown"}</span>
      </div>
      {url ? (
        <img src={url} alt={name} className="cam-frame" onError={() => setNonce((n) => n + 1)} />
      ) : (
        <div className="cam-frame placeholder">No frame yet</div>
      )}
    </div>
  );
}
