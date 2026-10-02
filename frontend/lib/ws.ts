/**
 * Origin to use for WebSocket connections.
 *
 * Priority: an explicit NEXT_PUBLIC_WS_URL, then a configured absolute API URL, and
 * otherwise the page's own origin. The server build leaves NEXT_PUBLIC_API_URL empty
 * precisely so sockets stay same-origin, which keeps live video off CORS entirely.
 */
export function wsBase(): string {
  const explicit = (process.env.NEXT_PUBLIC_WS_URL ?? "").trim().replace(/\/+$/, "");
  if (explicit) return explicit;

  const api = (process.env.NEXT_PUBLIC_API_URL ?? "").trim().replace(/\/+$/, "");
  if (/^https?:\/\//i.test(api)) return api.replace(/^http/, "ws");

  if (typeof window !== "undefined") {
    return (window.location.protocol === "https:" ? "wss://" : "ws://") + window.location.host;
  }
  return "";
}
