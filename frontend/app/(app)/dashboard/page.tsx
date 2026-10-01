"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ackAlert,
  listAlerts,
  listEvents,
  listSources,
  occupancy,
  type CameraSource,
  type EventItem,
  type OpenAlert,
  type Occupancy,
} from "@/lib/api";
import CameraFrame from "@/components/CameraFrame";
import LiveFeed from "@/components/LiveFeed";

const REFRESH_MS = 15000;

function startOfToday(): number {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d.getTime() / 1000;
}

function timeAgo(ts?: number): string {
  if (!ts) return "";
  const secs = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (secs < 60) return secs + "s ago";
  if (secs < 3600) return Math.floor(secs / 60) + "m ago";
  if (secs < 86400) return Math.floor(secs / 3600) + "h ago";
  return Math.floor(secs / 86400) + "d ago";
}

async function settle<T>(p: Promise<T>, fallback: T, note: (msg: string) => void): Promise<T> {
  try {
    return await p;
  } catch (err) {
    note(err instanceof Error ? err.message : "request failed");
    return fallback;
  }
}

export default function DashboardPage() {
  const [cameras, setCameras] = useState<CameraSource[]>([]);
  const [alerts, setAlerts] = useState<OpenAlert[]>([]);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [occ, setOcc] = useState<Occupancy | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [updated, setUpdated] = useState<number | null>(null);

  const load = useCallback(async () => {
    let problem = "";
    const note = (m: string) => {
      if (!problem) problem = m;
    };
    const [c, a, e, o] = await Promise.all([
      settle(listSources(), [] as CameraSource[], note),
      settle(listAlerts(50), [] as OpenAlert[], note),
      settle(listEvents(200), [] as EventItem[], note),
      settle(occupancy(), null as Occupancy | null, note),
    ]);
    setCameras(c);
    setAlerts(a);
    setEvents(e);
    setOcc(o);
    setError(problem);
    setUpdated(Date.now());
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, REFRESH_MS);
    return () => clearInterval(timer);
  }, [load]);

  async function onAck(id: number) {
    try {
      await ackAlert(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not acknowledge the alert");
    }
  }

  if (loading) {
    return (
      <main>
        <div className="page-head">
          <h1>Dashboard</h1>
        </div>
        <div className="metrics">
          {[0, 1, 2, 3].map((i) => (
            <div className="card metric" key={i}>
              <div className="skeleton" style={{ width: "55%", height: ".7rem" }} />
              <div className="skeleton" style={{ width: "35%", height: "1.6rem", marginTop: ".6rem" }} />
            </div>
          ))}
        </div>
        <div className="grid">
          {[0, 1].map((i) => (
            <div className="card" key={i}>
              <div className="skeleton" style={{ height: 170 }} />
            </div>
          ))}
        </div>
      </main>
    );
  }

  const online = cameras.filter((c) => c.running).length;
  const openAlerts = alerts.filter((a) => !a.resolved);
  const todayCount = events.filter((e) => (e.start_ts ?? 0) >= startOfToday()).length;

  return (
    <main>
      <div className="page-head">
        <h1>Dashboard</h1>
        <p className="sub">
          {updated ? "Updated " + new Date(updated).toLocaleTimeString() : ""} · refreshes every 15s
        </p>
      </div>

      {error && <div className="alert-error">Some data could not be loaded: {error}</div>}

      <div className="metrics">
        <div className="card metric">
          <div className="label">Cameras online</div>
          <div className="big">
            {online}
            <span className="muted" style={{ fontSize: "1rem", fontWeight: 500 }}> / {cameras.length}</span>
          </div>
        </div>
        <div className="card metric">
          <div className="label">Open alerts</div>
          <div className="big">{openAlerts.length}</div>
        </div>
        <div className="card metric">
          <div className="label">People on site</div>
          <div className="big">{occ ? occ.people : "—"}</div>
        </div>
        <div className="card metric">
          <div className="label">Events today</div>
          <div className="big">{todayCount}</div>
        </div>
      </div>

      <div className="dash-grid">
        <div>
          <h2>Cameras</h2>
          {cameras.length === 0 ? (
            <div className="empty">
              <div className="title">No cameras connected yet</div>
              <div>Add an RTSP camera or upload a video to start detecting.</div>
            </div>
          ) : (
            <div className="grid">
              {cameras.map((c) => (
                <CameraFrame key={c.id} sourceId={c.id} name={c.name ?? c.id} health={c.health} />
              ))}
            </div>
          )}

          <h2>Recent activity</h2>
          {events.length === 0 ? (
            <div className="empty">
              <div className="title">No events yet</div>
              <div>Detections appear here as soon as a camera sees something.</div>
            </div>
          ) : (
            <div className="card">
              <table className="table">
                <thead>
                  <tr>
                    <th>Event</th>
                    <th>Camera</th>
                    <th>When</th>
                  </tr>
                </thead>
                <tbody>
                  {events.slice(0, 8).map((ev) => (
                    <tr key={ev.id}>
                      <td>
                        <strong>{ev.event_type ?? "detection"}</strong>
                        {ev.top_object ? <span className="muted"> · {ev.top_object}</span> : null}
                      </td>
                      <td className="muted">{ev.camera_name ?? ev.camera_id}</td>
                      <td className="muted">{timeAgo(ev.start_ts)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div>
          <h2>Needs attention</h2>
          {openAlerts.length === 0 ? (
            <div className="empty">
              <div className="title">Nothing open</div>
              <div>Every alert has been handled.</div>
            </div>
          ) : (
            openAlerts.slice(0, 6).map((a) => (
              <div className="card" key={a.id}>
                <div className="cam-head">
                  <strong>{a.event_type ?? "alert"}</strong>
                  <span className={"badge " + (a.acknowledged ? "warn" : "danger")}>
                    {a.escalated ? "Escalated" : a.acknowledged ? "Acknowledged" : "New"}
                  </span>
                </div>
                <div className="muted" style={{ fontSize: ".85rem" }}>
                  {a.camera_name ?? a.camera_id} · {timeAgo(a.start_ts)}
                </div>
                {a.summary ? <p style={{ margin: ".5rem 0 0", fontSize: ".9rem" }}>{a.summary}</p> : null}
                <div className="row" style={{ margin: ".7rem 0 0" }}>
                  <button className="secondary btn-sm" onClick={() => onAck(a.id)}>
                    Acknowledge
                  </button>
                </div>
              </div>
            ))
          )}

          <h2>Live ticker</h2>
          <LiveFeed />
        </div>
      </div>
    </main>
  );
}
