"use client";

import { useState } from "react";
import { search, type EventItem } from "@/lib/api";

export default function SearchPage() {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<EventItem[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!q.trim()) return;
    setLoading(true);
    setError("");
    try {
      setResults(await search(q.trim()));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <h1>Smart search</h1>
      <p className="muted">Search by object (person, car), time (night, morning), or free text.</p>
      <form onSubmit={onSubmit} className="row">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. person at night" style={{ flex: 1 }} />
        <button type="submit" disabled={loading}>{loading ? "Searching…" : "Search"}</button>
      </form>
      {error && <p style={{ color: "#f87171" }}>{error}</p>}
      {results.map((ev) => (
        <div className="card" key={ev.id}>
          <strong>{ev.event_type ?? "detection"}</strong>
          <span className="muted"> · {ev.top_object ?? ""} · {ev.camera_name ?? ev.camera_id}</span>
          {ev.summary && <p>{ev.summary}</p>}
        </div>
      ))}
    </main>
  );
}
