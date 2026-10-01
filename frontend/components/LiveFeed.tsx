"use client";

import { useEffect, useState } from "react";
import { getToken } from "@/lib/api";

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "https://agay.tech").replace(/\/+$/, "");
const WS_URL = (process.env.NEXT_PUBLIC_WS_URL ?? API_URL).replace(/^http/, "ws");

export default function LiveFeed() {
  const [items, setItems] = useState<Record<string, unknown>[]>([]);

  useEffect(() => {
    const token = getToken();
    if (!token) return;
    const ws = new WebSocket(WS_URL + "/ws/events?token=" + encodeURIComponent(token));
    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        setItems((prev) => [data, ...prev].slice(0, 20));
      } catch {
        // ignore malformed messages
      }
    };
    return () => ws.close();
  }, []);

  if (items.length === 0) {
    return <p className="muted">Waiting for live events…</p>;
  }

  return (
    <div>
      {items.map((it, i) => (
        <div className="card" key={i}>
          <strong>{String(it.event_type ?? "detection")}</strong>
          <span className="muted"> · {String(it.camera_name ?? it.camera_id ?? "")}</span>
        </div>
      ))}
    </div>
  );
}
