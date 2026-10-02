"use client";

import { useCallback, useEffect, useState } from "react";
import { listEvents, listSources, type EventItem } from "@/lib/api";
import { timeAgo, fullTime } from "@/lib/format";
import ClipPlayer from "@/components/ClipPlayer";
import EventThumb from "@/components/EventThumb";
import PageHead from "@/components/PageHead";
import EmptyState from "@/components/EmptyState";

const TYPES = ["detection", "loitering", "intrusion", "queue", "fall", "abandoned", "parking"];
const PAGE = 50;

export default function EventsPage() {
  const [events, setEvents] = useState<EventItem[]>([]);
  const [cameras, setCameras] = useState<{ id: string; name: string }[]>([]);
  const [camera, setCamera] = useState("");
  const [etype, setEtype] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [limit, setLimit] = useState(PAGE);

  useEffect(() => {
    listSources()
      .then((s) => setCameras(s.map((c) => ({ id: c.id, name: c.name ?? c.id }))))
      .catch(() => {});
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    const filters: { camera_id?: string; event_type?: string } = {};
    if (camera) filters.camera_id = camera;
    if (etype) filters.event_type = etype;
    try {
      setEvents(await listEvents(limit, filters));
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load events");
    } finally {
      setLoading(false);
    }
  }, [camera, etype, limit]);

  useEffect(() => {
    load();
  }, [load]);

  const filtering = camera !== "" || etype !== "";

  return (
    <main>
      <PageHead
        title="Events"
        sub={events.length + " event" + (events.length === 1 ? "" : "s") + (filtering ? " matching your filters" : " recorded")}
        actions={
          <button className="secondary" onClick={load} disabled={loading}>
            {loading ? "Refreshing…" : "Refresh"}
          </button>
        }
      />

      <div className="row card">
        <select value={camera} onChange={(e) => setCamera(e.target.value)} style={{ minWidth: 180 }}>
          <option value="">All cameras</option>
          {cameras.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <select value={etype} onChange={(e) => setEtype(e.target.value)} style={{ minWidth: 160 }}>
          <option value="">All types</option>
          {TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        {(camera || etype) && (
          <button
            className="secondary btn-sm"
            onClick={() => {
              setCamera("");
              setEtype("");
            }}
          >
            Clear filters
          </button>
        )}
      </div>

      {error && <div className="alert-error">{error}</div>}

      {loading && events.length === 0 ? (
        <div className="card">
          <div className="skeleton" style={{ height: "5rem" }} />
        </div>
      ) : events.length === 0 ? (
        <EmptyState
          title={filtering ? "No events match those filters" : "No events yet"}
          hint={filtering ? "Try clearing the filters." : "Detections appear here once a camera is running."}
        />
      ) : (
        <>
          <div className="card">
            <table className="table">
              <thead>
                <tr>
                  <th style={{ width: 110 }} />
                  <th>Event</th>
                  <th>Camera</th>
                  <th>When</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {events.map((ev) => (
                  <tr key={ev.id}>
                    <td>
                      <EventThumb eventId={ev.id} />
                    </td>
                    <td>
                      <strong>{ev.event_type ?? "detection"}</strong>
                      {ev.top_object ? <span className="muted"> · {ev.top_object}</span> : null}
                      {ev.summary ? (
                        <div className="muted" style={{ fontSize: ".84rem", marginTop: ".2rem" }}>
                          {ev.summary}
                        </div>
                      ) : null}
                    </td>
                    <td className="muted">{ev.camera_name ?? ev.camera_id}</td>
                    <td className="muted" title={fullTime(ev.start_ts)}>
                      {timeAgo(ev.start_ts)}
                    </td>
                    <td style={{ textAlign: "right" }}>
                      <ClipPlayer eventId={ev.id} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {events.length >= limit && (
            <div className="row" style={{ justifyContent: "center" }}>
              <button className="secondary" onClick={() => setLimit(limit + PAGE)}>
                Show more
              </button>
            </div>
          )}
        </>
      )}
    </main>
  );
}
