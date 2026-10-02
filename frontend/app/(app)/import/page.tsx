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
import PageHead from "@/components/PageHead";
import EmptyState from "@/components/EmptyState";
import Badge from "@/components/Badge";

export default function ImportPage() {
  const [file, setFile] = useState<File | null>(null);
  const [fast, setFast] = useState(true);
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

  const finished = status?.status === "stopped";

  return (
    <main>
      <PageHead
        title="Import video"
        sub="Upload a recording and SmartCam will analyse it once and report what it found — useful for assessing a site before installing."
      />

      {!sourceId && (
        <form onSubmit={onImport} className="card">
          <div className="field">
            <label htmlFor="video">Video file</label>
            <input
              id="video"
              type="file"
              accept="video/*"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>

          <label className="row" style={{ gap: ".5rem", marginBottom: "1rem", color: "var(--text)" }}>
            <input type="checkbox" checked={fast} onChange={(e) => setFast(e.target.checked)} />
            <span>
              Fast processing
              <span className="muted" style={{ fontSize: ".85rem" }}> — analyse as quickly as possible instead of real time</span>
            </span>
          </label>

          <button type="submit" disabled={!file || busy}>
            {busy ? "Uploading…" : "Import and analyse"}
          </button>
        </form>
      )}

      {error && <div className="alert-error">{error}</div>}

      {sourceId && status && (
        <>
          <div className="card">
            <div className="cam-head">
              <strong>Assessment</strong>
              <span className="spread">
                <Badge tone={finished ? "ok" : status.status === "error" ? "danger" : "warn"}>
                  {status.status}
                </Badge>
                <button className="secondary btn-sm" onClick={onRemove}>
                  Remove
                </button>
              </span>
            </div>

            {frameUrl ? (
              <img src={frameUrl} alt="Assessment preview" className="cam-frame" />
            ) : (
              <div className="cam-frame placeholder">Warming up the model…</div>
            )}

            <div className="metrics" style={{ marginTop: "1rem", marginBottom: 0 }}>
              <div className="metric">
                <div className="label">Frames</div>
                <div className="big">{status.frames}</div>
              </div>
              <div className="metric">
                <div className="label">FPS</div>
                <div className="big">{(status.fps ?? 0).toFixed(1)}</div>
              </div>
              <div className="metric">
                <div className="label">Objects now</div>
                <div className="big">{status.active_objects?.length ?? 0}</div>
              </div>
              <div className="metric">
                <div className="label">Events found</div>
                <div className="big">{events.length}</div>
              </div>
            </div>

            {status.active_objects && status.active_objects.length > 0 && (
              <p className="muted" style={{ marginBottom: 0, fontSize: ".88rem" }}>
                Currently seeing: {status.active_objects.join(", ")}
              </p>
            )}
            {status.error ? <div className="alert-error" style={{ marginTop: "1rem" }}>{status.error}</div> : null}
          </div>

          {finished && (
            <>
              <h2>Results — {events.length} event{events.length === 1 ? "" : "s"}</h2>
              {events.length === 0 ? (
                <EmptyState
                  title="Nothing detected in this clip"
                  hint="Try a longer recording, or one with clearer movement."
                />
              ) : (
                <div className="card">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Event</th>
                        <th>Objects</th>
                      </tr>
                    </thead>
                    <tbody>
                      {events.map((ev) => (
                        <tr key={ev.id}>
                          <td>
                            <strong>{ev.event_type ?? "detection"}</strong>
                            {ev.summary ? (
                              <div className="muted" style={{ fontSize: ".85rem", marginTop: ".2rem" }}>
                                {ev.summary}
                              </div>
                            ) : null}
                          </td>
                          <td className="muted">{(ev.objects ?? []).join(", ") || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <p className="muted" style={{ fontSize: ".85rem" }}>
                Clips and thumbnails for these events are in the Events tab.
              </p>
            </>
          )}
        </>
      )}
    </main>
  );
}
