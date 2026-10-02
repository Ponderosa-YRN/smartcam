"use client";

import { useEffect, useMemo, useState } from "react";
import { listPlates, type Plate } from "@/lib/api";
import { fullTime } from "@/lib/format";
import PageHead from "@/components/PageHead";
import EmptyState from "@/components/EmptyState";
import Badge, { confTone } from "@/components/Badge";

export default function PlatesPage() {
  const [plates, setPlates] = useState<Plate[]>([]);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listPlates(200)
      .then(setPlates)
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load plates"))
      .finally(() => setLoading(false));
  }, []);

  const shown = useMemo(() => {
    const f = filter.trim().toUpperCase();
    if (!f) return plates;
    return plates.filter((p) => (p.plate ?? "").toUpperCase().includes(f));
  }, [plates, filter]);

  return (
    <main>
      <PageHead
        title="Plates"
        sub={plates.length + " number plate" + (plates.length === 1 ? "" : "s") + " read by ANPR"}
      />

      {error && <div className="alert-error">{error}</div>}

      {plates.length > 0 && (
        <div className="row">
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter by plate…"
            style={{ minWidth: 220 }}
          />
          {filter && <span className="muted">{shown.length} match{shown.length === 1 ? "" : "es"}</span>}
        </div>
      )}

      {loading ? (
        <div className="card">
          <div className="skeleton" style={{ height: "4rem" }} />
        </div>
      ) : plates.length === 0 ? (
        <EmptyState
          title="No plates read yet"
          hint="Number plates appear here once the ANPR model runs on a camera."
        />
      ) : shown.length === 0 ? (
        <EmptyState title="No plates match that filter" hint="Clear the filter to see them all." />
      ) : (
        <div className="card">
          <table className="table">
            <thead>
              <tr>
                <th>Plate</th>
                <th>Confidence</th>
                <th>Camera</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((p) => (
                <tr key={p.id}>
                  <td className="mono">
                    <strong>{p.plate}</strong>
                  </td>
                  <td>
                    <Badge tone={confTone(p.confidence)}>{(p.confidence * 100).toFixed(0)}%</Badge>
                  </td>
                  <td className="muted">{p.camera_name ?? p.camera_id}</td>
                  <td className="muted">{fullTime(p.ts)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
