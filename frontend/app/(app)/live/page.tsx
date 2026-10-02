"use client";

import { useCallback, useEffect, useState } from "react";
import { listSources, type CameraSource } from "@/lib/api";
import CameraFrame from "@/components/CameraFrame";
import WebRTCLiveFeed from "@/components/WebRTCLiveFeed";
import PageHead from "@/components/PageHead";
import EmptyState from "@/components/EmptyState";

const REFRESH_MS = 10000;
type Mode = "mjpeg" | "webrtc";

export default function LivePage() {
  const [cameras, setCameras] = useState<CameraSource[]>([]);
  const [error, setError] = useState("");
  const [mode, setMode] = useState<Mode>("mjpeg");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setCameras(await listSources());
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load cameras");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, REFRESH_MS);
    return () => clearInterval(timer);
  }, [load]);

  const online = cameras.filter((c) => c.running).length;

  return (
    <main>
      <PageHead
        title="Live view"
        sub={
          cameras.length === 0
            ? "No cameras configured."
            : online + " of " + cameras.length + " cameras online"
        }
        actions={
          <span className="tabs" style={{ marginBottom: 0, borderBottom: "none" }}>
            <button className={mode === "mjpeg" ? "active" : ""} onClick={() => setMode("mjpeg")}>
              Snapshot
            </button>
            <button className={mode === "webrtc" ? "active" : ""} onClick={() => setMode("webrtc")}>
              Realtime
            </button>
          </span>
        }
      />

      {error && <div className="alert-error">{error}</div>}

      {loading ? (
        <div className="grid">
          {[0, 1].map((i) => (
            <div className="card" key={i}>
              <div className="skeleton" style={{ height: 180 }} />
            </div>
          ))}
        </div>
      ) : cameras.length === 0 ? (
        <EmptyState
          title="No cameras yet"
          hint="Add an RTSP camera in Settings, or upload a video from the Import screen."
        />
      ) : (
        <div className="grid">
          {cameras.map((c) =>
            mode === "webrtc" ? (
              <WebRTCLiveFeed key={c.id} sourceId={c.id} name={c.name ?? c.id} />
            ) : (
              <CameraFrame key={c.id} sourceId={c.id} name={c.name ?? c.id} health={c.health} />
            )
          )}
        </div>
      )}

      <p className="muted" style={{ fontSize: ".82rem" }}>
        Snapshot mode refreshes every couple of seconds. Realtime mode uses WebRTC for lower
        latency and needs a camera that is actively running.
      </p>
    </main>
  );
}
