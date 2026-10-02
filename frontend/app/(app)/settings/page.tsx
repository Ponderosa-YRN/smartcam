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
import { SECTIONS, getPath, setPath, type Field } from "@/lib/settings-schema";
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
  ...SECTIONS.map((s) => ({ id: s.id, label: s.label })),
  { id: "advanced", label: "Advanced" },
];

/** Number input that keeps what you type locally, so decimals are typeable. */
function NumberControl({
  initial,
  field,
  onChange,
}: {
  initial: unknown;
  field: Field;
  onChange: (v: number) => void;
}) {
  const [text, setText] = useState(initial === undefined || initial === null ? "" : String(initial));
  return (
    <input
      type="number"
      value={text}
      step={field.step}
      min={field.min}
      max={field.max}
      onChange={(e) => {
        setText(e.target.value);
        const n = Number(e.target.value);
        if (e.target.value !== "" && !Number.isNaN(n)) onChange(n);
      }}
    />
  );
}

/** Comma-separated list editor. Leaves empty entries out of the saved value. */
function TagsControl({ initial, onChange }: { initial: unknown; onChange: (v: string[]) => void }) {
  const list = Array.isArray(initial) ? initial.map(String) : [];
  const [text, setText] = useState(list.join(", "));
  return (
    <input
      value={text}
      placeholder="comma separated"
      onChange={(e) => {
        setText(e.target.value);
        onChange(
          e.target.value
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean)
        );
      }}
    />
  );
}

function Control({
  field,
  cfg,
  onSet,
}: {
  field: Field;
  cfg: Cfg;
  onSet: (path: string, value: unknown) => void;
}) {
  const value = getPath(cfg, field.path);

  if (field.kind === "bool") {
    const on = Boolean(value);
    return (
      <label className="switch">
        <input
          type="checkbox"
          checked={on}
          onChange={(e) => onSet(field.path, e.target.checked)}
        />
        <span className="state">{on ? "On" : "Off"}</span>
      </label>
    );
  }

  if (field.kind === "select") {
    return (
      <select value={String(value ?? "")} onChange={(e) => onSet(field.path, e.target.value)}>
        {(field.options ?? []).map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    );
  }

  if (field.kind === "number") {
    return (
      <NumberControl
        initial={value}
        field={field}
        onChange={(n) => onSet(field.path, n)}
      />
    );
  }

  if (field.kind === "tags") {
    return <TagsControl initial={value} onChange={(v) => onSet(field.path, v)} />;
  }

  return (
    <input
      type={field.kind === "secret" ? "password" : "text"}
      value={value === undefined || value === null ? "" : String(value)}
      placeholder={field.kind === "secret" ? "•••• (leave to keep)" : undefined}
      onChange={(e) => onSet(field.path, e.target.value)}
    />
  );
}

/** Raw JSON escape hatch. Keeps its own text so half-typed JSON is not snatched away. */
function AdvancedEditor({ cfg, onChange }: { cfg: Cfg; onChange: (c: Cfg) => void }) {
  const [text, setText] = useState(() => JSON.stringify(cfg, null, 2));
  const [problem, setProblem] = useState("");

  return (
    <>
      <div className="card" style={{ borderColor: "rgba(245,158,11,.35)" }}>
        <strong style={{ color: "#fcd34d" }}>For technical users</strong>
        <p className="muted" style={{ fontSize: ".88rem", marginBottom: 0 }}>
          This is the raw configuration file. Everything the other tabs set lives here too —
          break the JSON and you can break the app, so prefer the friendly screens.
        </p>
      </div>

      {problem && <div className="alert-error">{problem}</div>}

      <div className="card">
        <textarea
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            try {
              onChange(JSON.parse(e.target.value) as Cfg);
              setProblem("");
            } catch {
              setProblem("That is not valid JSON yet. Your text is kept, but nothing is applied.");
            }
          }}
          rows={26}
          spellCheck={false}
          className="mono"
          style={{ fontSize: ".85rem", lineHeight: 1.5 }}
        />
      </div>
    </>
  );
}

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

      {tab === "advanced" && (
        <AdvancedEditor key={loadKey} cfg={cfg} onChange={(next) => setCfg(next)} />
      )}
    </main>
  );
}
