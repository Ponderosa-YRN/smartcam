"use client";

import { useEffect, useState } from "react";
import { getConfig, saveConfig } from "@/lib/api";
import PageHead from "@/components/PageHead";

export default function SettingsPage() {
  const [text, setText] = useState("");
  const [original, setOriginal] = useState("");
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  function reload() {
    setLoading(true);
    getConfig()
      .then((cfg) => {
        const t = JSON.stringify(cfg, null, 2);
        setText(t);
        setOriginal(t);
        setError("");
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load configuration"))
      .finally(() => setLoading(false));
  }

  useEffect(reload, []);

  const dirty = original !== "" && text !== original;

  function onFormat() {
    try {
      setText(JSON.stringify(JSON.parse(text), null, 2));
      setError("");
    } catch (e) {
      setError("Not valid JSON — " + (e instanceof Error ? e.message : "parse failed"));
    }
  }

  async function onSave() {
    setError("");
    setMsg("");
    try {
      const cfg = JSON.parse(text);
      await saveConfig(cfg);
      setOriginal(text);
      setMsg("Saved. The changes take effect after the API restarts.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid JSON");
    }
  }

  return (
    <main>
      <PageHead
        title="Settings"
        sub="The complete SmartCam configuration. Everything here is stored as JSON."
        actions={
          <>
            <button className="secondary" onClick={reload} disabled={loading}>
              Reload
            </button>
            <button className="secondary" onClick={onFormat} disabled={loading}>
              Format
            </button>
            <button onClick={onSave} disabled={loading || !dirty}>
              {dirty ? "Save changes" : "Saved"}
            </button>
          </>
        }
      />

      {error && <div className="alert-error">{error}</div>}
      {msg && <div className="flash">{msg}</div>}

      {dirty && !msg && (
        <div className="card" style={{ borderColor: "rgba(245,158,11,.4)", background: "rgba(245,158,11,.08)" }}>
          <span style={{ color: "#fcd34d" }}>You have unsaved changes.</span>
        </div>
      )}

      {loading ? (
        <div className="card">
          <div className="skeleton" style={{ height: 320 }} />
        </div>
      ) : (
        <div className="card">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={28}
            spellCheck={false}
            className="mono"
            style={{ fontSize: ".85rem", lineHeight: 1.5 }}
          />
        </div>
      )}

      <p className="muted" style={{ fontSize: ".85rem" }}>
        Saving writes the configuration to disk. Camera pipelines pick it up when the API
        restarts — so nothing changes live until then.
      </p>
    </main>
  );
}
