"use client";

import { useEffect, useState } from "react";
import { listAlerts, ackAlert, resolveAlert, type OpenAlert } from "@/lib/api";
import ClipPlayer from "@/components/ClipPlayer";

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<OpenAlert[]>([]);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");

  function reload() {
    listAlerts().then(setAlerts).catch((e) => setError(e.message));
  }
  useEffect(reload, []);

  async function act(fn: (id: number) => Promise<void>, id: number, label: string) {
    try {
      await fn(id);
      setMsg(label + " ok");
      reload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "error");
    }
  }

  return (
    <main>
      <h1>Alerts</h1>
      {error && <p style={{ color: "#f87171" }}>{error}</p>}
      {msg && <p className="muted">{msg}</p>}
      {alerts.length === 0 ? (
        <p className="muted">No open alerts.</p>
      ) : (
        alerts.map((a) => (
          <div className="card" key={a.id}>
            <strong>{a.event_type ?? "detection"}</strong>
            <span className="muted"> · {a.top_object ?? ""} · {a.camera_name ?? a.camera_id}</span>
            {a.escalated ? <span style={{ color: "#fbbf24" }}> · ESCALATED</span> : null}
            {a.assignee ? <span className="muted"> · assigned: {a.assignee}</span> : null}
            <div className="row" style={{ marginTop: "0.5rem", marginBottom: 0 }}>
              <button onClick={() => act(ackAlert, a.id, "Acknowledged")}>Acknowledge</button>
              <button className="secondary" onClick={() => act(resolveAlert, a.id, "Resolved")}>Resolve</button>
            </div>
            <ClipPlayer eventId={a.id} />
          </div>
        ))
      )}
    </main>
  );
}
