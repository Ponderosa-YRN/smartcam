"use client";

import { useEffect, useState } from "react";
import { listSources, type CameraSource } from "@/lib/api";
import CameraFrame from "@/components/CameraFrame";
import WebRTCLiveFeed from "@/components/WebRTCLiveFeed";

export default function LivePage() {
  const [cameras, setCameras] = useState<CameraSource[]>([]);
  const [error, setError] = useState("");
  const [mode, setMode] = useState<"mjpeg" | "webrtc">("mjpeg");

  useEffect(() => {
    listSources().then(setCameras).catch((e) => setError(e.message));
  }, []);

  return (
    <main>
      <h1>Live view</h1>
      <div className="row" style={{ marginBottom: "1rem" }}>
        <button className={mode === "mjpeg" ? "" : "secondary"} onClick={() => setMode("mjpeg")}>MJPEG</button>
        <button className={mode === "webrtc" ? "" : "secondary"} onClick={() => setMode("webrtc")}>WebRTC</button>
      </div>
      {error && <p style={{ color: "#f87171" }}>{error}</p>}
      {cameras.length === 0 ? (
        <p className="muted">No cameras configured.</p>
      ) : (
        <div className="grid">
          {cameras.map((c) => (
            mode === "webrtc"
              ? <WebRTCLiveFeed key={c.id} sourceId={c.id} />
              : <CameraFrame key={c.id} sourceId={c.id} name={c.name ?? c.id} health={c.health} />
          ))}
        </div>
      )}
    </main>
  );
}
