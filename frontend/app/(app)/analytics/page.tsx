"use client";

import { useEffect, useState } from "react";
import { occupancy, occupancyHistory, type Occupancy, type OccupancySample } from "@/lib/api";

export default function AnalyticsPage() {
  const [occ, setOcc] = useState<Occupancy | null>(null);
  const [history, setHistory] = useState<OccupancySample[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    occupancy().then(setOcc).catch((e) => setError(e.message));
    occupancyHistory(Date.now() / 1000 - 86400).then(setHistory).catch(() => {});
  }, []);

  return (
    <main>
      <h1>Analytics</h1>
      {error && <p style={{ color: "#f87171" }}>{error}</p>}
      {occ && (
        <div className="metrics">
          <div className="metric card"><div className="big">{occ.people}</div><div className="muted">People now</div></div>
          <div className="metric card"><div className="big">{occ.vehicles}</div><div className="muted">Vehicles now</div></div>
          <div className="metric card"><div className="big">{occ.entered ?? 0}</div><div className="muted">Entered today</div></div>
          <div className="metric card"><div className="big">{occ.left ?? 0}</div><div className="muted">Left today</div></div>
        </div>
      )}
      <h2>Occupancy history (24h)</h2>
      {history.length === 0 ? (
        <p className="muted">No samples.</p>
      ) : (
        <div className="card">
          <table className="table">
            <thead>
              <tr><th>Time</th><th>People</th><th>Vehicles</th></tr>
            </thead>
            <tbody>
              {history.slice(0, 50).map((h, i) => (
                <tr key={i}>
                  <td>{new Date(h.ts * 1000).toLocaleTimeString()}</td>
                  <td>{h.people}</td>
                  <td>{h.vehicles}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
