"use client";

import { useEffect, useState } from "react";
import { listEvents, type EventItem } from "@/lib/api";
import LiveFeed from "@/components/LiveFeed";

export default function DashboardPage() {
  const [events, setEvents] = useState<EventItem[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    listEvents(20).then(setEvents).catch((e) => setError(e.message));
  }, []);

  return (
    <main>
      <h1>Dashboard</h1>
      {error && <p style={{ color: "#f87171" }}>{error}</p>}
      <h2>Live feed</h2>
      <LiveFeed />
      <h2>Recent events</h2>
      {events.length === 0 ? (
        <p className="muted">No events yet.</p>
      ) : (
        events.map((ev) => (
          <div className="card" key={ev.id}>
            <strong>{ev.event_type ?? "detection"}</strong>
            <span className="muted"> · {ev.top_object ?? ""} · {ev.camera_name ?? ev.camera_id}</span>
            {ev.summary && <p>{ev.summary}</p>}
          </div>
        ))
      )}
    </main>
  );
}
