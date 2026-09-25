"use client";

import { useEffect, useRef, useState } from "react";
import {
  uploadVideo,
  createSource,
  startSource,
  stopSource,
  removeSource,
  getSourceStatus,
  fetchFrameBlob,
  listEvents,
  type SourceStatus,
  type EventItem,
} from "@/lib/api";

export default function ImportPage() {
  const [file, setFile] = useState<File | null>(null);
  const [fast, setFast] = useState(false);
  const [busy, setBusy] = useState(false);
  const [sourceId, setSourceId] = useState<string | null>(null);
  const [status, setStatus] = useState<SourceStatus | null>(null);
  const [frameUrl, setFrameUrl] = useState<string | null>(null);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [error, setError] = useState("");
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  function stopPolling() {
    if (timer.current) {
      clearInterval(timer.current);
      timer.current = null;
    }
  }

  useEffect(() => stopPolling, []);

  async function onImport(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setError("");
    setStatus(null);
    setEvents([]);
    setSourceId(null);
    setFrameUrl(null);
    try {
      const up = await uploadVideo(file);
      const id = "import_" + Date.now();
      await createSource({ id, name: "Import: " + file.name, uri: up.path, loop: false, fast: fast });
      await startSource(id);
      setSourceId(id);
      timer.current = setInterval(async () => {
        try {
          const st = await getSourceStatus(id);
          setStatus(st);
          try {
            const blob = await fetchFrameBlob(id);
            setFrameUrl((prev) => {
              if (prev) URL.revokeObjectURL(prev);
              return URL.createObjectURL(blob);
            });
          } catch {
            // frame not ready yet
          }
          if (st.status === "stopped" || st.status === "error") {
            stopPolling();
            const evs = await listEvents(50, { camera_id: id });
            setEvents(evs);
          }
        } catch (err) {
          stopPolling();
          setError(err instanceof Error ? err.message : "Status check failed");
        }
      }, 1000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setBusy(false);
    }
  }

  async function onRemove() {
    if (!sourceId) return;
    stopPolling();
    try {
      await stopSource(sourceId);
      await removeSource(sourceId);
    } catch {
      // source already gone
    }
    setSourceId(null);
    setStatus(null);
    setEvents([]);
    setFrameUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return null;
    });
  }

  return (
    <main>
      <h1>Import video for assessment</h1>
      <p className="muted">Upload a video and SmartCam will analyze it once (fast, single-pass) and report the events it finds.</p>

      {!sourceId && (
        <form onSubmit={onImport} className="row">
          <input type="file" accept="video/*" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          <button type="submit" disabled={!file || busy}>{busy ? "Importing…" : "Import & analyze"}</button>
        </form>
      )}

      {!sourceId && (
        <label className="row" style={{ gap: "0.5rem" }}>
          <input type="checkbox" checked={fast} onChange={(e) => setFast(e.target.checked)} />
          <span>⚡ Fast processing (skip real-time playback)</span>
        </label>
      )}

      {error && <p style={{ color: "#f87171" }}>{error}</p>}

      {status && (
        <div className="card">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h2 style={{ margin: 0 }}>Assessment</h2>
            <button className="secondary" onClick={onRemove}>Remove</button>
          </div>
          {frameUrl ? (
            <img src={frameUrl} alt="Live assessment" className="clip" />
          ) : (
            <p className="muted">Warming up the model — the live view will appear here…</p>
          )}
          <div className="metrics">
            <div className="metric"><div className="big">{status.status}</div><div className="muted">Status</div></div>
            <div className="metric"><div className="big">{status.frames}</div><div className="muted">Frames</div></div>
            <div className="metric"><div className="big">{(status.fps ?? 0).toFixed(1)}</div><div className="muted">FPS</div></div>
            <div className="metric"><div className="big">{status.active_objects?.length ?? 0}</div><div className="muted">Objects now</div></div>
          </div>
          {status.active_objects && status.active_objects.length > 0 && (
            <p><span className="muted">Active:</span> {status.active_objects.join(", ")}</p>
          )}
        </div>
      )}

      {status?.status === "stopped" && (
        <div className="card">
          <h2>✅ Assessment complete — {events.length} event(s)</h2>
          {events.length === 0 ? (
            <p className="muted">No events detected.</p>
          ) : (
            events.map((ev) => (
              <div className="card" key={ev.id}>
                <strong>{ev.event_type ?? "detection"}</strong>
                <span className="muted"> · {(ev.objects ?? []).join(", ")}</span>
                {ev.summary && <p>{ev.summary}</p>}
              </div>
            ))
          )}
          <p className="muted">Clips and thumbnails are available in the Events tab.</p>
        </div>
      )}
    </main>
  );
}
