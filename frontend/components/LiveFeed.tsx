"use client";

import { useEffect, useState } from "react";
import { getToken } from "@/lib/api";
import { wsBase } from "@/lib/ws";
import { timeAgo } from "@/lib/format";

interface LiveItem {
  id?: number;
  event_type?: string;
  camera_name?: string;
  camera_id?: string;
  start_ts?: number;
  top_object?: string;
}

export default function LiveFeed() {
  const [items, setItems] = useState<LiveItem[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const token = getToken();
    if (!token) return;

    let ws: WebSocket | null = null;
    let closed = false;
    let retry: ReturnType<typeof setTimeout> | null = null;

    function connect() {
      if (closed) return;
      const url = wsBase() + "/ws/events?token=" + encodeURIComponent(token as string);
      ws = new WebSocket(url);
      ws.onopen = () => setConnected(true);
      ws.onmessage = (e) => {
        try {
          setItems((prev) => [JSON.parse(e.data) as LiveItem, ...prev].slice(0, 15));
        } catch {
          // ignore malformed messages
        }
      };
      ws.onclose = () => {
        setConnected(false);
        if (!closed) retry = setTimeout(connect, 4000);
      };
      ws.onerror = () => {
        try {
          ws?.close();
        } catch {
          // ignore
        }
      };
    }

    connect();
    return () => {
      closed = true;
      if (retry) clearTimeout(retry);
      try {
        ws?.close();
      } catch {
        // ignore
      }
    };
  }, []);

  if (items.length === 0) {
    return (
      <div className="card" style={{ textAlign: "center", color: "var(--text-dim)", fontSize: ".9rem" }}>
        <span className={"live-dot"} style={{ background: connected ? "var(--ok)" : "var(--text-dim)" }} />{" "}
        {connected ? "Listening for detections…" : "Connecting…"}
      </div>
    );
  }

  return (
    <div>
      {items.map((it, i) => (
        <div className="card" key={it.id ?? i} style={{ padding: ".6rem .8rem" }}>
          <strong>{it.event_type ?? "detection"}</strong>
          {it.top_object ? <span className="muted"> · {it.top_object}</span> : null}
          <div className="muted" style={{ fontSize: ".8rem" }}>
            {it.camera_name ?? it.camera_id ?? ""}
            {it.start_ts ? " · " + timeAgo(it.start_ts) : ""}
          </div>
        </div>
      ))}
    </div>
  );
}
