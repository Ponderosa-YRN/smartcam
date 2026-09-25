"use client";

import { useEffect, useState } from "react";
import { listEvents, listSources, type EventItem } from "@/lib/api";
import ClipPlayer from "@/components/ClipPlayer";

const TYPES = ["detection", "loitering", "intrusion", "queue", "fall", "abandoned", "parking"];

export default function EventsPage() {
  const [events, setEvents] = useState<EventItem[]>([]);
  const [cameras, setCameras] = useState<{ id: string; name: string }[]>([]);
  const [camera, setCamera] = useState("");
  const [etype, setEtype] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    listSources()
      .then((s) => setCameras(s.map((c) => ({ id: c.id, name: c.name ?? c.id }))))
      .catch(() => {});
  }, []);

  useEffect(() => {
    const filters: { camera_id?: string; event_type?: string } = {};
    if (camera) filters.camera_id = camera;
    if (etype) filters.event_type = etype;
    listEvents(100, filters).then(setEvents).catch((e) => setError(e.message));
  }, [camera, etype]);

  return (
    <main>
      <h1>Events</h1>
      <div className="row">
        <select value={camera} onChange={(e) => setCamera(e.target.value)}>
          <option value="">All cameras</option>
          {cameras.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
        <select value={etype} onChange={(e) => setEtype(e.target.value)}>
          <option value="">All types</option>
          {TYPES.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </div>
      {error && <p style={{ color: "#f87171" }}>{error}</p>}
      {events.length === 0 ? (
        <p className="muted">No events.</p>
      ) : (
        events.map((ev) => (
          <div className="card" key={ev.id}>
            <strong>{ev.event_type ?? "detection"}</strong>
            <span className="muted"> · {ev.top_object ?? ""} · {ev.camera_name ?? ev.camera_id}</span>
            {ev.start_ts ? <span className="muted"> · {new Date(ev.start_ts * 1000).toLocaleString()}</span> : null}
            {ev.summary && <p>{ev.summary}</p>}
            <ClipPlayer eventId={ev.id} />
          </div>
        ))
      )}
    </main>
  );
}
