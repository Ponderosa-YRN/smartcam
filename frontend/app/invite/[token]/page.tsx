"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getInvitePreview, acceptInvite, type InvitePreview } from "@/lib/api";

export default function InviteAcceptPage() {
  const { token } = useParams<{ token: string }>();
  const router = useRouter();
  const [preview, setPreview] = useState<InvitePreview | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!token) return;
    getInvitePreview(token).then(setPreview).catch((e) => setError(e.message));
  }, [token]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await acceptInvite(token, username.trim(), password);
      router.replace("/login");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to accept invite");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={{ maxWidth: 420 }}>
      <h1>🎥 SmartCam</h1>
      {preview ? (
        <>
          <p>
            You have been invited to join <strong>{preview.tenant}</strong> as{" "}
            <strong>{preview.role}</strong> ({preview.email}).
          </p>
          <form onSubmit={onSubmit}>
            <div className="field">
              <label htmlFor="username">Choose a username</label>
              <input id="username" value={username} onChange={(e) => setUsername(e.target.value)} required />
            </div>
            <div className="field">
              <label htmlFor="password">Choose a password</label>
              <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>
            {error && <p style={{ color: "#f87171" }}>{error}</p>}
            <button type="submit" disabled={loading} style={{ width: "100%" }}>
              {loading ? "Creating account…" : "Accept invite"}
            </button>
          </form>
        </>
      ) : (
        !error && <p className="muted">Loading invite…</p>
      )}
      {error && !preview && <p style={{ color: "#f87171" }}>{error}</p>}
    </main>
  );
}
