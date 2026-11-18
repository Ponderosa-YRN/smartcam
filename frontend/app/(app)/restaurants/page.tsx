"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { listTables, serviceTable, type RestaurantTable } from "@/lib/api";
import PageHead from "@/components/PageHead";
import EmptyState from "@/components/EmptyState";

const POLL_MS = 5000;
// Two missed polls and the display is no longer trustworthy.
const STALE_AFTER_SEC = 15;

function clock(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
}

/**
 * Floor view of restaurant tables.
 *
 * The server measures waiting time; the browser advances it between polls so the clock ticks
 * every second without asking the API every second.
 */
export default function RestaurantsPage() {
  const [tables, setTables] = useState<RestaurantTable[]>([]);
  const [fetchedAt, setFetchedAt] = useState(0);
  const [, setTick] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    try {
      setTables(await listTables());
      setFetchedAt(Date.now());
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load tables");
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    load();
    const poll = setInterval(load, POLL_MS);
    const ticker = setInterval(() => setTick((t) => t + 1), 1000);
    return () => {
      clearInterval(poll);
      clearInterval(ticker);
    };
  }, [load]);

  async function onService(id: string) {
    setBusy(id);
    try {
      await serviceTable(id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not mark the table serviced");
    } finally {
      setBusy(null);
    }
  }

  // If the server stops answering, the clock must stop with it: advancing a timer on no data
  // would show a table "waiting 12:30" when the system has no idea what is happening.
  const fetchedAgeSec = fetchedAt ? (Date.now() - fetchedAt) / 1000 : 0;
  const stale = fetchedAt > 0 && fetchedAgeSec > STALE_AFTER_SEC;
  const drift = stale ? 0 : fetchedAgeSec;
  const seatedCount = tables.filter((t) => t.seated).length;
  // Threshold is per table, so the header counts waiting tables without claiming a time.
  const flaggedCount = tables.filter((t) => t.flagged).length;

  return (
    <main>
      <PageHead
        title="Restaurants"
        sub={
          tables.length === 0
            ? "No tables configured."
            : seatedCount + " of " + tables.length + " tables seated" +
              (flaggedCount ? " · " + flaggedCount + " waiting for attention" : "")
        }
      />

      {error && <div className="alert-error">{error}</div>}

      {stale && (
        <div className="alert-error">
          Showing the last known state — the server has not answered for{" "}
          {Math.round(fetchedAgeSec)}s, so the timers are frozen.
        </div>
      )}

      {loaded && tables.length === 0 && (
        <EmptyState
          title="No tables yet"
          hint="In Settings → Zones, draw a polygon over each table and tick the restaurant table option."
        />
      )}

      <div className="grid">
        {tables.map((t) => {
          const waiting = t.seated ? t.waiting_sec + drift : 0;
          const tone = t.flagged ? "danger" : t.seated ? "warn" : "ok";
          return (
            <div
              className="card"
              key={t.id}
              style={{ borderColor: t.flagged ? "var(--danger)" : undefined }}
            >
              <div className="cam-head">
                <strong>{t.name}</strong>
                <span className={"badge " + tone}>
                  {t.flagged ? "waiting" : t.seated ? "seated" : "free"}
                </span>
              </div>
              <div className="muted" style={{ fontSize: ".85rem", marginBottom: ".6rem" }}>
                {t.seats ? t.seats + " seats · " : ""}
                {t.occupancy} detected · {t.camera_id}
              </div>
              <div className="big" style={{ fontVariantNumeric: "tabular-nums" }}>
                {t.seated ? clock(waiting) : "—"}
              </div>
              <div className="muted" style={{ fontSize: ".78rem", marginBottom: ".6rem" }}>
                {t.seated ? "since seated or last served" : "table free"}
              </div>
              <button
                className="secondary btn-sm"
                disabled={!t.seated || busy === t.id}
                onClick={() => onService(t.id)}
                style={{ width: "100%" }}
              >
                {busy === t.id ? "Saving…" : "Table serviced"}
              </button>
            </div>
          );
        })}
      </div>

      <p className="muted" style={{ fontSize: ".82rem" }}>
        A table turns red once a party has waited longer than the threshold without being marked
        serviced. Detection comes from the camera, so a table hidden behind a pillar may read
        free. Use “Table serviced” when staff have attended — that restarts the clock.
      </p>
    </main>
  );
}
