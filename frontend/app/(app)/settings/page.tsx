"use client";

import { useEffect, useState } from "react";
import { getConfig, saveConfig } from "@/lib/api";

export default function SettingsPage() {
  const [text, setText] = useState("");
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  function reload() {
    getConfig()
      .then((cfg) => setText(JSON.stringify(cfg, null, 2)))
      .catch((e) => setError(e.message));
  }
  useEffect(reload, []);

  async function onSave() {
    setError("");
    setMsg("");
    try {
      const cfg = JSON.parse(text);
      await saveConfig(cfg);
      setMsg("Saved. Changes take effect after the API restarts.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid JSON");
    }
  }

  return (
    <main>
      <h1>Settings</h1>
      <p className="muted">Edit the full configuration as JSON. Saving requires an API restart to take effect.</p>
      <div className="row">
        <button className="secondary" onClick={reload}>Reload</button>
        <button onClick={onSave}>Save</button>
      </div>
      {error && <p style={{ color: "#f87171" }}>{error}</p>}
      {msg && <p className="muted">{msg}</p>}
      <textarea value={text} onChange={(e) => setText(e.target.value)} rows={30} />
    </main>
  );
}
