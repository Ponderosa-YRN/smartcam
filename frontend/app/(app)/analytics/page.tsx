"use client";

import { useEffect, useMemo, useState } from "react";
import { occupancy, occupancyHistory, type Occupancy, type OccupancySample } from "@/lib/api";
import PageHead from "@/components/PageHead";
import EmptyState from "@/components/EmptyState";

const DAY = 86400;

function Series({ data, colour, height = 140 }: { data: number[]; colour: string; height?: number }) {
  if (data.length < 2) return null;
  const W = 600;
  const H = height;
  const max = Math.max(1, ...data);
  const step = W / (data.length - 1);
  const y = (v: number) => H - 6 - (v / max) * (H - 16);
  const line = data.map((v, i) => (i === 0 ? "M" : "L") + (i * step).toFixed(1) + " " + y(v).toFixed(1)).join(" ");
  const area = line + " L" + W + " " + H + " L0 " + H + " Z";
  return (
    <svg viewBox={"0 0 " + W + " " + H} preserveAspectRatio="none" style={{ width: "100%", height: H, display: "block" }}>
      <path d={area} fill={colour} opacity="0.14" />
      <path d={line} fill="none" stroke={colour} strokeWidth="2" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

/** Keep charts readable - never plot more than ~240 points. */
function thin(samples: OccupancySample[]): OccupancySample[] {
  if (samples.length <= 240) return samples;
  const stride = Math.ceil(samples.length / 240);
  return samples.filter((_, i) => i % stride === 0);
}

export default function AnalyticsPage() {
  const [occ, setOcc] = useState<Occupancy | null>(null);
  const [history, setHistory] = useState<OccupancySample[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      occupancy().catch(() => null),
      occupancyHistory(Date.now() / 1000 - DAY, 2000).catch(() => [] as OccupancySample[]),
    ])
      .then(([o, h]) => {
        setOcc(o);
        setHistory(h);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load analytics"))
      .finally(() => setLoading(false));
  }, []);

  const stats = useMemo(() => {
    const people = history.map((h) => h.people);
    const vehicles = history.map((h) => h.vehicles);
    const peak = people.length ? Math.max(...people) : 0;
    const avg = people.length ? people.reduce((a, b) => a + b, 0) / people.length : 0;
    return { peak, avg, vehicles };
  }, [history]);

  const plot = useMemo(() => thin(history), [history]);

  if (loading) {
    return (
      <main>
        <PageHead title="Analytics" sub="Footfall and occupancy over the last 24 hours." />
        <div className="metrics">
          {[0, 1, 2, 3].map((i) => (
            <div className="card metric" key={i}>
              <div className="skeleton" style={{ width: "55%", height: ".7rem" }} />
              <div className="skeleton" style={{ width: "35%", height: "1.6rem", marginTop: ".6rem" }} />
            </div>
          ))}
        </div>
        <div className="card">
          <div className="skeleton" style={{ height: 140 }} />
        </div>
      </main>
    );
  }

  return (
    <main>
      <PageHead title="Analytics" sub="Footfall and occupancy over the last 24 hours." />

      {error && <div className="alert-error">{error}</div>}

      <div className="metrics">
        <div className="card metric">
          <div className="label">People now</div>
          <div className="big">{occ ? occ.people : "—"}</div>
        </div>
        <div className="card metric">
          <div className="label">Vehicles now</div>
          <div className="big">{occ ? occ.vehicles : "—"}</div>
        </div>
        <div className="card metric">
          <div className="label">Entered today</div>
          <div className="big">{occ?.entered ?? "—"}</div>
        </div>
        <div className="card metric">
          <div className="label">Left today</div>
          <div className="big">{occ?.left ?? "—"}</div>
        </div>
        <div className="card metric">
          <div className="label">Peak (24h)</div>
          <div className="big">{stats.peak}</div>
        </div>
        <div className="card metric">
          <div className="label">Average (24h)</div>
          <div className="big">{stats.avg.toFixed(1)}</div>
        </div>
      </div>

      {history.length === 0 ? (
        <EmptyState
          title="No occupancy samples yet"
          hint="Counts are recorded as cameras detect people and vehicles."
        />
      ) : (
        <>
          <h2>People</h2>
          <div className="card chart-card">
            <div className="chart-legend">
              <span>
                <span className="swatch" style={{ background: "var(--brand)" }} />
                People on site
              </span>
              <span className="muted" style={{ marginLeft: "auto" }}>
                peak {stats.peak}
              </span>
            </div>
            <Series data={plot.map((h) => h.people)} colour="#3b82f6" />
          </div>

          <h2>Vehicles</h2>
          <div className="card chart-card">
            <div className="chart-legend">
              <span>
                <span className="swatch" style={{ background: "#22c55e" }} />
                Vehicles on site
              </span>
              <span className="muted" style={{ marginLeft: "auto" }}>
                peak {Math.max(0, ...stats.vehicles)}
              </span>
            </div>
            <Series data={plot.map((h) => h.vehicles)} colour="#22c55e" />
          </div>

          <p className="muted" style={{ fontSize: ".82rem" }}>
            {history.length} samples · showing {plot.length} points
          </p>
        </>
      )}
    </main>
  );
}
