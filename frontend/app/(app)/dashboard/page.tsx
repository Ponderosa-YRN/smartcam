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
import { startOfToday, timeAgo } from "@/lib/format";

const REFRESH_MS = 15000;

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
        <Metric
          label="Cameras online"
          gradient="grad-blue"
          icon={<IconCamera />}
          value={online}
          sub={"/ " + cameras.length}
        />
        <Metric
          label="Open alerts"
          gradient="grad-amber"
          icon={<IconAlert />}
          value={openAlerts.length}
        />
        <Metric
          label="People on site"
          gradient="grad-violet"
          icon={<IconPeople />}
          value={occ ? occ.people : "—"}
        />
        <Metric
          label="Vehicles on site"
          gradient="grad-emerald"
          icon={<IconVehicle />}
          value={occ ? occ.vehicles : "—"}
        />
        <Metric
          label="Events today"
          gradient="grad-rose"
          icon={<IconActivity />}
          value={todayCount}
        />
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


/* -- KPI tile and its icons ------------------------------------------------ */

function Metric({
  label,
  value,
  sub,
  gradient,
  icon,
}: {
  label: string;
  value: number | string;
  sub?: string;
  gradient: string;
  icon: React.ReactNode;
}) {
  // <article> because the tile is a self-contained piece of content, not a generic
  // container. Regions stay direct children so the container query can place them.
  return (
    <article className="card metric">
      <span className={"metric-icon " + gradient} aria-hidden="true">
        {icon}
      </span>
      <div className="metric-body">
        <div className="label">{label}</div>
        <div className="big">
          {value}
          {sub && <span className="metric-sub">{sub}</span>}
        </div>
      </div>
    </article>
  );
}

/* Inline SVG rather than an icon dependency: four paths are cheaper than a
   package, and they inherit currentColor. Decorative, so aria-hidden on the chip. */
const iconProps = {
  width: 20,
  height: 20,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

function IconCamera() {
  return (
    <svg {...iconProps}>
      <path d="M2.5 7.5h11a1.5 1.5 0 0 1 1.5 1.5v6a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 1 15v-6a1.5 1.5 0 0 1 1.5-1.5Z" />
      <path d="m15 11 5.2-2.6a.8.8 0 0 1 1.3.7v5.8a.8.8 0 0 1-1.3.7L15 13" />
    </svg>
  );
}

function IconAlert() {
  return (
    <svg {...iconProps}>
      <path d="M10.3 3.9 2.4 17.4A2 2 0 0 0 4.1 20.4h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />
      <path d="M12 9v4" />
      <path d="M12 16.5h.01" />
    </svg>
  );
}

function IconPeople() {
  return (
    <svg {...iconProps}>
      <path d="M16 20v-1.6a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4V20" />
      <circle cx="9" cy="7" r="3.4" />
      <path d="M22 20v-1.6a4 4 0 0 0-3-3.87" />
      <path d="M16.5 4.2a3.4 3.4 0 0 1 0 6.4" />
    </svg>
  );
}

function IconVehicle() {
  return (
    <svg {...iconProps}>
      <path d="M4.5 16.5V12l1.8-4.6A2 2 0 0 1 8.2 6h7.6a2 2 0 0 1 1.9 1.4L19.5 12v4.5" />
      <path d="M3 12h18" />
      <circle cx="7.5" cy="17.5" r="1.8" />
      <circle cx="16.5" cy="17.5" r="1.8" />
    </svg>
  );
}

function IconActivity() {
  return (
    <svg {...iconProps}>
      <path d="M3 12h3.5l2.5-7 4 14 2.5-7H21" />
    </svg>
  );
}

