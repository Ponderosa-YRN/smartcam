"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { login } from "@/lib/api";

// Stamped at build time so it is obvious whether the browser is showing a freshly
// deployed page or a stale cached one.
const BUILD = (
  process.env.NEXT_PUBLIC_VERCEL_GIT_COMMIT_SHA ??
  process.env.NEXT_PUBLIC_BUILD ??
  "dev"
).slice(0, 7);

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(username, password);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
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
            <p className="sub">Sign in to your dashboard</p>
          </div>
        </div>

        <form onSubmit={onSubmit}>
          <div className="field">
            <label htmlFor="username">Username</label>
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
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              style={{ width: "100%" }}
              required
            />
          </div>

          {error && <div className="alert-error">{error}</div>}

          <button type="submit" disabled={loading} style={{ width: "100%" }}>
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <p className="muted" style={{ marginTop: "1rem", fontSize: ".88rem" }}>
          New here? <Link href="/register">Create an account</Link>
        </p>
        <p className="muted" style={{ marginTop: ".6rem", fontSize: ".7rem", opacity: 0.5 }}>
          build {BUILD}
        </p>
      </div>
    </main>
  );
}
