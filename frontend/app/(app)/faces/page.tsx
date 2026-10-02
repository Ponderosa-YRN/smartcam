"use client";

import { useEffect, useState } from "react";
import { listFaces, listFaceMatches, type Face, type FaceMatch } from "@/lib/api";
import { timeAgo } from "@/lib/format";
import PageHead from "@/components/PageHead";
import EmptyState from "@/components/EmptyState";
import Badge, { confTone } from "@/components/Badge";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

export default function FacesPage() {
  const [faces, setFaces] = useState<Face[]>([]);
  const [matches, setMatches] = useState<FaceMatch[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      listFaces().catch(() => [] as Face[]),
      listFaceMatches(100).catch(() => [] as FaceMatch[]),
    ])
      .then(([f, m]) => {
        setFaces(f);
        setMatches(m);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load faces"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main>
      <PageHead
        title="Faces"
        sub={faces.length + " registered · " + matches.length + " recent match" + (matches.length === 1 ? "" : "es")}
      />

      {error && <div className="alert-error">{error}</div>}

      <h2>Registered people</h2>
      {loading ? (
        <div className="card">
          <div className="skeleton" style={{ height: "3rem" }} />
        </div>
      ) : faces.length === 0 ? (
        <EmptyState
          title="Nobody registered yet"
          hint="Register a person from the Import screen to start matching faces."
        />
      ) : (
        <div className="grid">
          {faces.map((f) => (
            <div className="card" key={f.id} style={{ marginBottom: 0 }}>
              <div className="spread">
                <span className="avatar">{initials(f.name ?? "")}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <strong>{f.name}</strong>
                  <div className="muted" style={{ fontSize: ".85rem" }}>{f.role || "—"}</div>
                </div>
                <Badge tone={f.consent ? "ok" : "warn"}>{f.consent ? "Consent" : "No consent"}</Badge>
              </div>
            </div>
          ))}
        </div>
      )}

      <h2>Recent matches</h2>
      {loading ? (
        <div className="card">
          <div className="skeleton" style={{ height: "3rem" }} />
        </div>
      ) : matches.length === 0 ? (
        <EmptyState title="No matches yet" hint="Matches appear when a registered face is recognised on a camera." />
      ) : (
        <div className="card">
          <table className="table">
            <thead>
              <tr>
                <th>Person</th>
                <th>Camera</th>
                <th>Confidence</th>
                <th>When</th>
              </tr>
            </thead>
            <tbody>
              {matches.map((m) => (
                <tr key={m.id}>
                  <td><strong>{m.name}</strong></td>
                  <td className="muted">{m.camera_name ?? m.camera_id}</td>
                  <td><Badge tone={confTone(m.confidence)}>{(m.confidence * 100).toFixed(0)}%</Badge></td>
                  <td className="muted">{timeAgo(m.ts)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
