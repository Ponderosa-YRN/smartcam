"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ackAlert,
  assignAlert,
  escalateAlert,
  listAlerts,
  resolveAlert,
  type OpenAlert,
} from "@/lib/api";
import { timeAgo } from "@/lib/format";
import ClipPlayer from "@/components/ClipPlayer";

const REFRESH_MS = 20000;
type Filter = "new" | "acknowledged" | "escalated" | "all";

const FILTERS: [Filter, string][] = [
  ["new", "Needs attention"],
  ["acknowledged", "Acknowledged"],
  ["escalated", "Escalated"],
  ["all", "All open"],
];

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<OpenAlert[]>([]);
  const [filter, setFilter] = useState<Filter>("new");
  const [error, setError] = useState("");
  const [flash, setFlash] = useState("");
  const [busy, setBusy] = useState<number | null>(null);
  const [assignFor, setAssignFor] = useState<number | null>(null);
  const [assignee, setAssignee] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setAlerts(await listAlerts(200));
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load alerts");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, REFRESH_MS);
    return () => clearInterval(timer);
  }, [load]);

  useEffect(() => {
    if (!flash) return;
    const t = setTimeout(() => setFlash(""), 3500);
    return () => clearTimeout(t);
  }, [flash]);

  async function act(id: number, label: string, fn: (id: number) => Promise<void>) {
    setBusy(id);
    try {
      await fn(id);
      setFlash(label);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed");
    } finally {
      setBusy(null);
    }
  }

  const counts = useMemo(
    () => ({
      new: alerts.filter((a) => !a.acknowledged && !a.escalated).length,
      acknowledged: alerts.filter((a) => a.acknowledged && !a.escalated).length,
      escalated: alerts.filter((a) => a.escalated).length,
      all: alerts.length,
    }),
    [alerts]
  );

  const shown = useMemo(() => {
    if (filter === "new") return alerts.filter((a) => !a.acknowledged && !a.escalated);
    if (filter === "acknowledged") return alerts.filter((a) => a.acknowledged && !a.escalated);
    if (filter === "escalated") return alerts.filter((a) => a.escalated);
    return alerts;
  }, [alerts, filter]);

  if (loading) {
    return (
      <main>
        <div className="page-head">
          <h1>Alerts</h1>
        </div>
        {[0, 1, 2].map((i) => (
          <div className="card" key={i}>
            <div className="skeleton" style={{ width: "40%", height: ".9rem" }} />
            <div className="skeleton" style={{ width: "65%", height: ".8rem", marginTop: ".6rem" }} />
            <div className="skeleton" style={{ width: "28%", height: "1.4rem", marginTop: ".8rem" }} />
          </div>
        ))}
      </main>
    );
  }

  return (
    <main>
      <div className="page-head">
        <h1>Alerts</h1>
        <p className="sub">Open items that still need a decision. Refreshes every 20s.</p>
      </div>

      {error && <div className="alert-error">{error}</div>}
      {flash && <div className="flash">{flash}</div>}

      <div className="tabs">
        {FILTERS.map(([key, label]) => (
          <button key={key} className={filter === key ? "active" : ""} onClick={() => setFilter(key)}>
            {label}
            <span className="n">{counts[key]}</span>
          </button>
        ))}
      </div>

      {shown.length === 0 ? (
        <div className="empty">
          <div className="title">{filter === "all" ? "No open alerts" : "Nothing in this list"}</div>
          <div>
            {filter === "all"
              ? "Every alert has been resolved."
              : "Try another tab, or check All open."}
          </div>
        </div>
      ) : (
        shown.map((a) => (
          <div className="card" key={a.id}>
            <div className="cam-head">
              <div>
                <strong>{a.event_type ?? "detection"}</strong>
                {a.top_object ? <span className="muted"> · {a.top_object}</span> : null}
              </div>
              <span className={"badge " + (a.acknowledged && !a.escalated ? "warn" : "danger")}>
                {a.escalated ? "Escalated" : a.acknowledged ? "Acknowledged" : "New"}
              </span>
            </div>

            <div className="muted" style={{ fontSize: ".85rem" }}>
              {a.camera_name ?? a.camera_id} · {timeAgo(a.start_ts)}
              {a.assignee ? " · assigned to " + a.assignee : ""}
            </div>

            {a.summary ? <p style={{ margin: ".55rem 0 0", fontSize: ".92rem" }}>{a.summary}</p> : null}

            <div className="alert-actions">
              <button
                className="btn-sm"
                disabled={busy === a.id || !!a.acknowledged}
                onClick={() => act(a.id, "Alert acknowledged", ackAlert)}
              >
                Acknowledge
              </button>
              <button
                className="secondary btn-sm"
                disabled={busy === a.id || !!a.escalated}
                onClick={() => act(a.id, "Alert escalated", escalateAlert)}
              >
                Escalate
              </button>
              <button
                className="secondary btn-sm"
                disabled={busy === a.id}
                onClick={() => {
                  setAssignFor(assignFor === a.id ? null : a.id);
                  setAssignee(a.assignee ?? "");
                }}
              >
                Assign
              </button>
              <button
                className="secondary btn-sm"
                disabled={busy === a.id}
                onClick={() => act(a.id, "Alert resolved", resolveAlert)}
              >
                Resolve
              </button>
              <ClipPlayer eventId={a.id} />
            </div>

            {assignFor === a.id && (
              <div className="assign-row">
                <input
                  value={assignee}
                  onChange={(e) => setAssignee(e.target.value)}
                  placeholder="Name or email"
                />
                <button
                  className="btn-sm"
                  disabled={!assignee.trim() || busy === a.id}
                  onClick={async () => {
                    const who = assignee.trim();
                    await act(a.id, "Assigned to " + who, (id) => assignAlert(id, who));
                    setAssignFor(null);
                  }}
                >
                  Save
                </button>
              </div>
            )}
          </div>
        ))
      )}
    </main>
  );
}
