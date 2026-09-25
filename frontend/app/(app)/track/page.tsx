"use client";

import { useEffect, useState } from "react";
import { listIdentities, listSightings, type Identity, type Sighting } from "@/lib/api";

export default function TrackPage() {
  const [ids, setIds] = useState<Identity[]>([]);
  const [sel, setSel] = useState<number | null>(null);
  const [sightings, setSightings] = useState<Sighting[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    listIdentities().then(setIds).catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (sel == null) return;
    listSightings(sel).then(setSightings).catch(() => {});
  }, [sel]);

  return (
    <main>
      <h1>Track person (ReID)</h1>
      {error && <p style={{ color: "#f87171" }}>{error}</p>}
      <div className="row">
        <select value={sel ?? ""} onChange={(e) => setSel(e.target.value ? Number(e.target.value) : null)}>
          <option value="">Select identity…</option>
          {ids.map((id) => (
            <option key={id.id} value={id.id}>{id.name}</option>
          ))}
        </select>
      </div>
      {sel != null && (
        <>
          <h2>Sightings ({sightings.length})</h2>
          {sightings.map((s) => (
            <div className="card" key={s.id}>
              <strong>{s.camera_name ?? s.camera_id}</strong>
              <span className="muted"> · {(s.confidence * 100).toFixed(0)}% · {new Date(s.ts * 1000).toLocaleString()}</span>
            </div>
          ))}
        </>
      )}
    </main>
  );
}
