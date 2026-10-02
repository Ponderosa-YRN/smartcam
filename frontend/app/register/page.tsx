"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { register } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [company, setCompany] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await register(company.trim(), username.trim(), password);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
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
            <p className="sub">Create your organisation account</p>
          </div>
        </div>

        <form onSubmit={onSubmit}>
          <div className="field">
            <label htmlFor="company">Company / hotel name</label>
            <input
              id="company"
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              style={{ width: "100%" }}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="username">Admin username</label>
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
              autoComplete="new-password"
              style={{ width: "100%" }}
              required
            />
          </div>

          {error && <div className="alert-error">{error}</div>}

          <button type="submit" disabled={loading} style={{ width: "100%" }}>
            {loading ? "Creating…" : "Create account"}
          </button>
        </form>

        <p className="muted" style={{ marginTop: "1rem", fontSize: ".88rem" }}>
          Already have an account? <Link href="/login">Sign in</Link>
        </p>
      </div>
    </main>
  );
}
