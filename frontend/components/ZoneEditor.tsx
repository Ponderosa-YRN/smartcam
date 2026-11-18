"use client";

import { useEffect, useState } from "react";
import { fetchFrameBlob, type CameraSource } from "@/lib/api";
import { ZONE_FIELDS } from "@/lib/settings-schema";
import Control from "@/components/SettingsFields";
import Badge from "@/components/Badge";

export type ZoneRow = {
  id: string;
  name: string;
  source_id: string;
  points: number[][];
  classes: string[];
  max_occupancy?: number | null;
  loiter_sec?: number | null;
  restricted: boolean;
  allowed_window: string;
  parking: boolean;
  capacity?: number | null;
};

const round4 = (n: number) => Math.round(n * 10000) / 10000;

export default function ZoneEditor({
  zone,
  cameras,
  onChange,
  onRemove,
}: {
  zone: ZoneRow;
  cameras: CameraSource[];
  onChange: (patch: Partial<ZoneRow>) => void;
  onRemove: () => void;
}) {
  const points = Array.isArray(zone.points) ? zone.points : [];
  const frameCamera = zone.source_id || cameras[0]?.id || "";
  const [frameUrl, setFrameUrl] = useState<string | null>(null);
  const [aspect, setAspect] = useState(16 / 9);

  useEffect(() => {
    if (!frameCamera) return;
    let alive = true;
    let made: string | null = null;
    fetchFrameBlob(frameCamera)
      .then((b) => {
        if (!alive) return;
        made = URL.createObjectURL(b);
        setFrameUrl(made);
      })
      .catch(() => {
        /* no frame yet - the surface stays blank and still accepts points */
      });
    return () => {
      alive = false;
      if (made) URL.revokeObjectURL(made);
    };
  }, [frameCamera]);

  function place(e: React.MouseEvent<HTMLDivElement>) {
    const r = e.currentTarget.getBoundingClientRect();
    const x = round4(Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)));
    const y = round4(Math.min(1, Math.max(0, (e.clientY - r.top) / r.height)));
    onChange({ points: [...points, [x, y]] });
  }

  return (
    <div className="card">
      <div className="cam-head">
        <strong>{zone.name || "Zone"}</strong>
        <span className="spread">
          <Badge tone={points.length >= 3 ? "ok" : "warn"}>
            {points.length} point{points.length === 1 ? "" : "s"}
          </Badge>
          <button className="secondary btn-sm" onClick={onRemove}>
            Remove
          </button>
        </span>
      </div>

      <div className="field">
        <label>Which camera</label>
        <select
          value={zone.source_id ?? ""}
          onChange={(e) => onChange({ source_id: e.target.value })}
          style={{ width: "100%" }}
        >
          <option value="">All cameras</option>
          {cameras.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name ?? c.id}
            </option>
          ))}
        </select>
      </div>

      <div className="field">
        <label>Shape — click to place a corner; three or more close the shape</label>
        <div className="zone-surface" onClick={place} style={{ aspectRatio: String(aspect) }}>
          {frameUrl ? (
            <img
              src={frameUrl}
              alt=""
              onLoad={(e) => {
                const t = e.currentTarget;
                if (t.naturalWidth) setAspect(t.naturalWidth / t.naturalHeight);
              }}
            />
          ) : (
            <div className="zone-empty">
              No picture from this camera yet. You can still place corners — they will sit on
              the frame once it starts.
            </div>
          )}

          <div className="zone-grid" />
          <div className="zone-scrim" />

          <svg
            viewBox="0 0 1 1"
            preserveAspectRatio="none"
            style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
          >
            {/* Dashed guide while placing, so two corners already show a direction. */}
            {points.length > 1 && (
              <polyline
                className="zone-path"
                points={points.map((p) => p[0] + "," + p[1]).join(" ")}
                vectorEffect="non-scaling-stroke"
              />
            )}
            {points.length > 2 && (
              <polygon
                className="zone-shape"
                points={points.map((p) => p[0] + "," + p[1]).join(" ")}
                vectorEffect="non-scaling-stroke"
              />
            )}
          </svg>

          {points.map((p, i) => (
            <span
              key={i}
              className="zone-vertex-dot"
              style={{ left: (p[0] * 100).toFixed(2) + "%", top: (p[1] * 100).toFixed(2) + "%" }}
            />
          ))}
        </div>

        <div className="row" style={{ margin: ".6rem 0 0" }}>
          <button
            className="secondary btn-sm"
            disabled={points.length === 0}
            onClick={() => onChange({ points: points.slice(0, -1) })}
          >
            Undo last point
          </button>
          <button className="secondary btn-sm" disabled={points.length === 0} onClick={() => onChange({ points: [] })}>
            Clear shape
          </button>
          {points.length > 0 && points.length < 3 && (
            <span className="muted" style={{ fontSize: ".82rem" }}>
              A zone needs at least 3 points before it can match anything.
            </span>
          )}
        </div>
      </div>

      {ZONE_FIELDS.map((f) => (
        <div className="setting" key={f.path}>
          <div className="meta">
            <div className="name">{f.label}</div>
            {f.help ? <div className="help">{f.help}</div> : null}
          </div>
          <div className="control">
            <Control
              field={f}
              cfg={zone}
              onSet={(path, value) => onChange({ [path]: value } as Partial<ZoneRow>)}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
