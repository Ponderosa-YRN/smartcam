"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getConfig,
  saveConfig,
  listSources,
  startSource,
  stopSource,
  type CameraSource,
} from "@/lib/api";
import { SECTIONS, setPath } from "@/lib/settings-schema";
import Control from "@/components/SettingsFields";
import ZoneEditor, { type ZoneRow } from "@/components/ZoneEditor";
import PageHead from "@/components/PageHead";
import EmptyState from "@/components/EmptyState";
import Badge from "@/components/Badge";

type Cfg = Record<string, unknown>;

interface SourceRow {
  id: string;
  name: string;
  uri: string;
  enabled: boolean;
  loop: boolean;
  fast: boolean;
}

const TABS = [
  { id: "cameras", label: "Cameras" },
  { id: "zones", label: "Zones" },
  ...SECTIONS.map((s) => ({ id: s.id, label: s.label })),
];

export default function SettingsPage() {
  const [cfg, setCfg] = useState<Cfg | null>(null);
  const [saved, setSaved] = useState("");
  const [tab, setTab] = useState("cameras");
  const [error, setError] = useState("");
  const [flash, setFlash] = useState("");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadKey, setLoadKey] = useState(0);
  const [live, setLive] = useState<CameraSource[]>([]);

  const reload = useCallback(() => {
    setLoading(true);
    getConfig()
      .then((c) => {
        const obj = c as Cfg;
        setCfg(obj);
        setSaved(JSON.stringify(obj));
        setError("");
        setLoadKey((k) => k + 1);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load settings"))
      .finally(() => setLoading(false));
    listSources()
      .then(setLive)
      .catch(() => {});
  }, []);

  useEffect(reload, [reload]);

  useEffect(() => {
    if (!flash) return;
    const t = setTimeout(() => setFlash(""), 9000);
    return () => clearTimeout(t);
  }, [flash]);

  const set = (path: string, value: unknown) => {
    setCfg((prev) => (prev ? setPath(prev, path, value) : prev));
  };

  const dirty = cfg !== null && JSON.stringify(cfg) !== saved;

  async function onSave() {
    if (!cfg) return;
    setSaving(true);
    setError("");
    setFlash("");
    try {
      await saveConfig(cfg);
      setSaved(JSON.stringify(cfg));
      setFlash(
        "Saved. These settings are picked up when the API restarts — run:  docker restart smartcam"
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save settings");
    } finally {
      setSaving(false);
    }
  }

  async function toggleCamera(id: string, running: boolean) {
    setError("");
    try {
      if (running) await stopSource(id);
      else await startSource(id);
      setLive(await listSources());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not change the camera");
    }
  }

  if (loading || !cfg) {
    return (
      <main>
        <PageHead title="Settings" sub="Loading configuration…" />
        <div className="card">
          <div className="skeleton" style={{ height: 220 }} />
        </div>
      </main>
    );
  }

  const sources = (Array.isArray(cfg.sources) ? cfg.sources : []) as SourceRow[];
  const zones = (Array.isArray(cfg.zones) ? cfg.zones : []) as ZoneRow[];

  const updateSource = (i: number, patch: Partial<SourceRow>) =>
    set(
      "sources",
      sources.map((s, idx) => (idx === i ? { ...s, ...patch } : s))
    );

  const addCamera = () =>
    set("sources", [
      ...sources,
      {
        id: "camera_" + Date.now(),
        name: "New camera",
        uri: "",
        enabled: true,
        loop: true,
        fast: false,
      },
    ]);

  const removeCamera = (i: number) =>
    set(
      "sources",
      sources.filter((_, idx) => idx !== i)
    );

  const updateZone = (i: number, patch: Partial<ZoneRow>) =>
    set(
      "zones",
      zones.map((z, idx) => (idx === i ? { ...z, ...patch } : z))
    );

  const removeZone = (i: number) =>
    set(
      "zones",
      zones.filter((_, idx) => idx !== i)
    );

  const addZone = () =>
    set("zones", [
      ...zones,
      {
        id: "zone_" + Date.now(),
        name: "Zone " + (zones.length + 1),
        source_id: "",
        points: [],
        classes: ["person"],
        max_occupancy: 0,
        loiter_sec: 0,
        restricted: false,
        allowed_window: "",
        parking: false,
        capacity: 0,
      },
    ]);

  const section = SECTIONS.find((s) => s.id === tab);

  return (
    <main>
      <PageHead
        title="Settings"
        sub="Everything SmartCam does, explained in plain language."
        actions={
          <>
            <button className="secondary" onClick={reload} disabled={saving}>
              Discard changes
            </button>
            <button onClick={onSave} disabled={saving || !dirty}>
              {saving ? "Saving…" : dirty ? "Save changes" : "Saved"}
            </button>
          </>
        }
      />

      {error && <div className="alert-error">{error}</div>}
      {flash && <div className="flash">{flash}</div>}
      {dirty && !flash && (
        <div
          className="card"
          style={{ borderColor: "rgba(245,158,11,.4)", background: "rgba(245,158,11,.08)" }}
        >
          <span style={{ color: "#fcd34d" }}>You have unsaved changes.</span>
        </div>
      )}

      <div className="tabs">
        {TABS.map((t) => (
          <button key={t.id} className={tab === t.id ? "active" : ""} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "cameras" && (
        <>
          <p className="muted" style={{ marginTop: 0 }}>
            Each camera is a video source. Use an <span className="mono">rtsp://</span> URL for a
            network camera, a file path for a recording, or a number for a webcam attached to this
            server.
          </p>

          {sources.length === 0 ? (
            <EmptyState title="No cameras configured" hint="Add your first camera below." />
          ) : (
            sources.map((s, i) => {
              const status = live.find((l) => l.id === s.id);
              return (
                <div className="card" key={s.id + "-" + i}>
                  <div className="cam-head">
                    <strong>{s.name || s.id}</strong>
                    <span className="spread">
                      {status ? (
                        <Badge tone={status.running ? "ok" : "warn"}>
                          {status.running ? "Running" : status.health || "stopped"}
                        </Badge>
                      ) : (
                        <Badge tone="warn">Not active yet</Badge>
                      )}
                      {status ? (
                        <button
                          className="secondary btn-sm"
                          onClick={() => toggleCamera(status.id, status.running)}
                        >
                          {status.running ? "Stop" : "Start"}
                        </button>
                      ) : null}
                      <button className="secondary btn-sm" onClick={() => removeCamera(i)}>
                        Remove
                      </button>
                    </span>
                  </div>

                  <div className="field">
                    <label>Name</label>
                    <input
                      value={s.name}
                      onChange={(e) => updateSource(i, { name: e.target.value })}
                      style={{ width: "100%" }}
                    />
                  </div>

                  <div className="field">
                    <label>Stream URL</label>
                    <input
                      value={s.uri}
                      placeholder="rtsp://user:pass@192.168.1.50:554/stream1"
                      onChange={(e) => updateSource(i, { uri: e.target.value })}
                      className="mono"
                      style={{ width: "100%" }}
                    />
                    <div className="muted" style={{ fontSize: ".8rem", marginTop: ".25rem" }}>
                      Examples: <span className="mono">rtsp://admin:pass@10.0.0.5:554/Streaming/Channels/101</span>{" "}
                      · <span className="mono">/app/data/uploads/clip.mp4</span> · <span className="mono">0</span>
                    </div>
                  </div>

                  <div className="row" style={{ marginBottom: 0 }}>
                    <label className="switch">
                      <input
                        type="checkbox"
                        checked={s.enabled}
                        onChange={(e) => updateSource(i, { enabled: e.target.checked })}
                      />
                      <span className="state">Enabled</span>
                    </label>
                    <label className="switch">
                      <input
                        type="checkbox"
                        checked={s.loop}
                        onChange={(e) => updateSource(i, { loop: e.target.checked })}
                      />
                      <span className="state">Loop</span>
                    </label>
                    <label className="switch">
                      <input
                        type="checkbox"
                        checked={s.fast}
                        onChange={(e) => updateSource(i, { fast: e.target.checked })}
                      />
                      <span className="state">Fast</span>
                    </label>
                  </div>
                </div>
              );
            })
          )}

          <button className="secondary" onClick={addCamera}>
            + Add camera
          </button>
        </>
      )}

      {tab === "zones" && (
        <>
          <p className="muted" style={{ marginTop: 0 }}>
            A zone is part of a camera&apos;s view with its own rules — somewhere nobody should be
            after hours, a queue that should not grow, a car park with a capacity. Click on the
            picture to draw the corners, then set the rules underneath.
          </p>

          {zones.length === 0 ? (
            <EmptyState title="No zones yet" hint="Add one below, then click the picture to draw it." />
          ) : (
            zones.map((z, i) => (
              <ZoneEditor
                key={z.id + "-" + i}
                zone={z}
                cameras={live}
                onChange={(patch) => updateZone(i, patch)}
                onRemove={() => removeZone(i)}
              />
            ))
          )}

          <button className="secondary" onClick={addZone}>
            + Add zone
          </button>
        </>
      )}

      {section && (
        <div key={loadKey}>
          {section.blurb ? (
            <p className="muted" style={{ marginTop: 0 }}>
              {section.blurb}
            </p>
          ) : null}
          {section.blocks.map((b) => (
            <div className="card" key={b.title}>
              <h3>{b.title}</h3>
              {b.note ? (
                <p className="muted" style={{ fontSize: ".85rem", marginTop: 0 }}>
                  {b.note}
                </p>
              ) : null}
              {b.fields.map((f) => (
                <div className="setting" key={f.path}>
                  <div className="meta">
                    <div className="name">{f.label}</div>
                    {f.help ? <div className="help">{f.help}</div> : null}
                  </div>
                  <div className="control">
                    <Control field={f} cfg={cfg} onSet={set} />
                  </div>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
