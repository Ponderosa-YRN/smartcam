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
    getInvitePreview(token)
      .then(setPreview)
      .catch((e) => setError(e instanceof Error ? e.message : "Invalid invite"));
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
    <main className="auth-wrap">
      <div className="auth-card">
        <div className="auth-brand">
          <span className="mark" style={{ width: 34, height: 34, fontSize: 16 }}>
            ◉
          </span>
          <div>
            <h1>SmartCam</h1>
            <p className="sub">Join your team</p>
          </div>
        </div>

        {preview ? (
          <>
            <div className="card">
              You have been invited to join <strong>{preview.tenant}</strong> as{" "}
              <strong>{preview.role}</strong>.
              <div className="muted" style={{ fontSize: ".85rem", marginTop: ".2rem" }}>
                {preview.email}
              </div>
            </div>

            <form onSubmit={onSubmit}>
              <div className="field">
                <label htmlFor="username">Choose a username</label>
                <input
                  id="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="username"
                  style={{ width: "100%" }}
                  required
                />
              </div>
              <div className="field">
                <label htmlFor="password">Choose a password</label>
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="new-password"
                  style={{ width: "100%" }}
                  required
                />
              </div>

              {error && <div className="alert-error">{error}</div>}

              <button type="submit" disabled={loading} style={{ width: "100%" }}>
                {loading ? "Creating account…" : "Accept invite"}
              </button>
            </form>
          </>
        ) : error ? (
          <div className="alert-error">{error}</div>
        ) : (
          <div className="boot" style={{ minHeight: "auto", padding: "2rem 0" }}>
            <div className="boot-spinner" />
            <span className="muted">Loading invite…</span>
          </div>
        )}
      </div>
    </main>
  );
}
