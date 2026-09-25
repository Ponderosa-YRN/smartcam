"use client";

import { useEffect, useState } from "react";
import { listFaces, listFaceMatches, type Face, type FaceMatch } from "@/lib/api";

export default function FacesPage() {
  const [faces, setFaces] = useState<Face[]>([]);
  const [matches, setMatches] = useState<FaceMatch[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    listFaces().then(setFaces).catch((e) => setError(e.message));
    listFaceMatches(100).then(setMatches).catch(() => {});
  }, []);

  return (
    <main>
      <h1>Faces</h1>
      {error && <p style={{ color: "#f87171" }}>{error}</p>}
      <h2>Registered ({faces.length})</h2>
      {faces.length === 0 ? (
        <p className="muted">None registered.</p>
      ) : (
        faces.map((f) => (
          <div className="card" key={f.id}>
            <strong>{f.name}</strong>
            <span className="muted"> · {f.role}{f.consent ? " · consent" : " · no consent"}</span>
          </div>
        ))
      )}
      <h2>Recent matches ({matches.length})</h2>
      {matches.map((m) => (
        <div className="card" key={m.id}>
          <strong>{m.name}</strong>
          <span className="muted"> · {m.camera_name ?? m.camera_id} · {(m.confidence * 100).toFixed(0)}%</span>
        </div>
      ))}
    </main>
  );
}
