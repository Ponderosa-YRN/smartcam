"use client";

import { useEffect, useRef, useState } from "react";
import { getToken, getWebRTCConfig } from "@/lib/api";
import { wsBase } from "@/lib/ws";

export default function WebRTCLiveFeed({ sourceId, name }: { sourceId: string; name?: string }) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [failed, setFailed] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    let ws: WebSocket | null = null;
    let pc: RTCPeerConnection | null = null;
    let cancelled = false;

    (async () => {
      let iceServers: RTCIceServer[] = [{ urls: "stun:stun.l.google.com:19302" }];
      try {
        const cfg = await getWebRTCConfig();
        if (!cfg.enabled) {
          setFailed(true);
          return;
        }
        if (cfg.ice_servers && cfg.ice_servers.length > 0) {
          iceServers = cfg.ice_servers.map((s) => ({
            urls: s.urls,
            username: s.username,
            credential: s.credential,
          }));
        }
      } catch {
        // fall back to the default STUN server
      }
      if (cancelled) return;

      const token = getToken() ?? "";
      const wsUrl = wsBase() + "/ws/webrtc/" + sourceId + "?token=" + encodeURIComponent(token);

      pc = new RTCPeerConnection({ iceServers });
      ws = new WebSocket(wsUrl);

      pc.ontrack = (ev) => {
        if (ev.streams && ev.streams[0]) {
          video.srcObject = ev.streams[0];
          setReady(true);
        }
      };
      pc.onicecandidate = (ev) => {
        if (ev.candidate && ws) {
          ws.send(
            JSON.stringify({
              type: "candidate",
              candidate: ev.candidate.candidate,
              sdpMid: ev.candidate.sdpMid,
              sdpMLineIndex: ev.candidate.sdpMLineIndex,
            })
          );
        }
      };
      ws.onopen = async () => {
        const offer = await pc!.createOffer();
        await pc!.setLocalDescription(offer);
        ws!.send(JSON.stringify({ type: "offer", sdp: pc!.localDescription ? pc!.localDescription.sdp : "" }));
      };
      ws.onmessage = async (e) => {
        try {
          const msg = JSON.parse(e.data);
          if (msg.type === "answer") {
            await pc!.setRemoteDescription({ type: "answer", sdp: msg.sdp });
          } else if (msg.type === "candidate") {
            await pc!.addIceCandidate({
              candidate: msg.candidate,
              sdpMid: msg.sdpMid,
              sdpMLineIndex: msg.sdpMLineIndex,
            });
          } else if (msg.type === "error") {
            setFailed(true);
          }
        } catch {
          // ignore malformed signaling
        }
      };
      ws.onerror = () => setFailed(true);
    })();

    return () => {
      cancelled = true;
      try {
        ws?.close();
      } catch {
        // ignore
      }
      try {
        pc?.close();
      } catch {
        // ignore
      }
    };
  }, [sourceId]);

  return (
    <div className="card">
      <div className="cam-head">
        <strong>{name ?? sourceId}</strong>
        <span className={"badge " + (failed ? "danger" : ready ? "ok" : "warn")}>
          {failed ? "Unavailable" : ready ? "Realtime" : "Connecting"}
        </span>
      </div>
      {failed ? (
        <div className="cam-frame placeholder">WebRTC unavailable for this camera.</div>
      ) : (
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className="cam-frame"
          style={{ objectFit: "contain" }}
        />
      )}
    </div>
  );
}
