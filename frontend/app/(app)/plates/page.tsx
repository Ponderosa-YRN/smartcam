"use client";

import { useEffect, useState } from "react";
import { listPlates, type Plate } from "@/lib/api";

export default function PlatesPage() {
  const [plates, setPlates] = useState<Plate[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    listPlates().then(setPlates).catch((e) => setError(e.message));
  }, []);

  return (
    <main>
      <h1>Plates (ANPR)</h1>
      {error && <p style={{ color: "#f87171" }}>{error}</p>}
      {plates.length === 0 ? (
        <p className="muted">No plates read yet.</p>
      ) : (
        <table className="table">
          <thead>
            <tr><th>Plate</th><th>Confidence</th><th>Camera</th><th>Time</th></tr>
          </thead>
          <tbody>
            {plates.map((p) => (
              <tr key={p.id}>
                <td><strong>{p.plate}</strong></td>
                <td>{(p.confidence * 100).toFixed(0)}%</td>
                <td>{p.camera_name ?? p.camera_id}</td>
                <td>{new Date(p.ts * 1000).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
}
