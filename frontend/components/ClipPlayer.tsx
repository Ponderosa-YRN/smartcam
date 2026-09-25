"use client";

import { useState } from "react";
import { fetchClipBlob } from "@/lib/api";

export default function ClipPlayer({ eventId }: { eventId: number }) {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const blob = await fetchClipBlob(eventId);
      setUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return URL.createObjectURL(blob);
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "clip unavailable");
    } finally {
      setLoading(false);
    }
  }

  function close() {
    setUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return null;
    });
  }

  if (url) {
    return (
      <div>
        <video src={url} controls autoPlay className="clip" />
        <br />
        <button className="secondary" onClick={close}>Close</button>
      </div>
    );
  }

  return (
    <div>
      <button className="secondary" onClick={load} disabled={loading}>
        {loading ? "Loading…" : "▶ Play clip"}
      </button>
      {error && <span className="muted"> · {error}</span>}
    </div>
  );
}
