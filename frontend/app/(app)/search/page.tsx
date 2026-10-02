"use client";

import { useState } from "react";
import { search, type EventItem } from "@/lib/api";
import { timeAgo } from "@/lib/format";
import PageHead from "@/components/PageHead";
import EmptyState from "@/components/EmptyState";

const EXAMPLES = ["person at night", "car", "today", "loitering", "after 6pm"];

export default function SearchPage() {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<EventItem[] | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function run(term: string) {
    if (!term.trim()) return;
    setLoading(true);
    setError("");
    try {
      setResults(await search(term.trim()));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <PageHead
        title="Smart search"
        sub="Search by object (person, car), time (night, morning) or free text."
      />

      <form
        className="row"
        onSubmit={(e) => {
          e.preventDefault();
          run(q);
        }}
      >
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="e.g. person at night"
          style={{ flex: 1, minWidth: 220 }}
        />
        <button type="submit" disabled={loading || !q.trim()}>
          {loading ? "Searching…" : "Search"}
        </button>
      </form>

      <div className="row" style={{ gap: ".4rem" }}>
        <span className="muted" style={{ fontSize: ".85rem" }}>Try:</span>
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            type="button"
            className="chip"
            onClick={() => {
              setQ(ex);
              run(ex);
            }}
          >
            {ex}
          </button>
        ))}
      </div>

      {error && <div className="alert-error">{error}</div>}

      {loading && (
        <div className="card">
          <div className="skeleton" style={{ width: "45%", height: ".9rem" }} />
          <div className="skeleton" style={{ width: "70%", height: ".8rem", marginTop: ".6rem" }} />
        </div>
      )}

      {!loading && results === null && (
        <EmptyState title="Nothing searched yet" hint="Enter a term above, or pick one of the examples." />
      )}

      {!loading && results !== null && results.length === 0 && (
        <EmptyState title={"No matches for “" + q + "”"} hint="Try a broader term, or a different time of day." />
      )}

      {!loading && results !== null && results.length > 0 && (
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
              {results.map((ev) => (
                <tr key={ev.id}>
                  <td>
                    <strong>{ev.event_type ?? "detection"}</strong>
                    {ev.top_object ? <span className="muted"> · {ev.top_object}</span> : null}
                    {ev.summary ? (
                      <div className="muted" style={{ fontSize: ".85rem", marginTop: ".2rem" }}>
                        {ev.summary}
                      </div>
                    ) : null}
                  </td>
                  <td className="muted">{ev.camera_name ?? ev.camera_id}</td>
                  <td className="muted">{timeAgo(ev.start_ts)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
