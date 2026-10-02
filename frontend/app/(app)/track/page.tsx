"use client";

import { useEffect, useState } from "react";
import { listIdentities, listSightings, type Identity, type Sighting } from "@/lib/api";
import { fullTime } from "@/lib/format";
import PageHead from "@/components/PageHead";
import EmptyState from "@/components/EmptyState";
import Badge, { confTone } from "@/components/Badge";

export default function TrackPage() {
  const [ids, setIds] = useState<Identity[]>([]);
  const [sel, setSel] = useState<number | null>(null);
  const [sightings, setSightings] = useState<Sighting[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    listIdentities()
      .then(setIds)
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load identities"));
  }, []);

  useEffect(() => {
    if (sel == null) {
      setSightings([]);
      return;
    }
    setLoading(true);
    listSightings(sel, 200)
      .then(setSightings)
      .catch(() => setSightings([]))
      .finally(() => setLoading(false));
  }, [sel]);

  const selected = ids.find((i) => i.id === sel);

  return (
    <main>
      <PageHead
        title="Track person"
        sub="Follow one person's movement across every camera, using re-identification."
      />

      {error && <div className="alert-error">{error}</div>}

      <div className="row">
        <select
          value={sel ?? ""}
          onChange={(e) => setSel(e.target.value ? Number(e.target.value) : null)}
          style={{ minWidth: 260 }}
        >
          <option value="">Select a person…</option>
          {ids.map((i) => (
            <option key={i.id} value={i.id}>
              {i.name}
            </option>
          ))}
        </select>
        {sel != null && (
          <span className="muted">
            {sightings.length} sighting{sightings.length === 1 ? "" : "s"}
          </span>
        )}
      </div>

      {ids.length === 0 ? (
        <EmptyState
          title="No identities yet"
          hint="Identities are created when you register a person in Import."
        />
      ) : sel == null ? (
        <EmptyState title="Pick a person" hint="Choose someone above to see where they have been seen." />
      ) : loading ? (
        <div className="card">
          <div className="skeleton" style={{ height: "3rem" }} />
        </div>
      ) : sightings.length === 0 ? (
        <EmptyState
          title={"No sightings for " + (selected?.name ?? "this person")}
          hint="They have not been recognised on any camera yet."
        />
      ) : (
        <div className="card">
          <table className="table">
            <thead>
              <tr>
                <th>Camera</th>
                <th>Confidence</th>
                <th>When</th>
              </tr>
            </thead>
            <tbody>
              {sightings.map((s) => (
                <tr key={s.id}>
                  <td><strong>{s.camera_name ?? s.camera_id}</strong></td>
                  <td><Badge tone={confTone(s.confidence)}>{(s.confidence * 100).toFixed(0)}%</Badge></td>
                  <td className="muted">{fullTime(s.ts)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
