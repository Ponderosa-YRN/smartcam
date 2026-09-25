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
    <main style={{ maxWidth: 360 }}>
      <h1>🎥 SmartCam</h1>
      <p className="muted">Create your organization account.</p>
      <form onSubmit={onSubmit}>
        <div className="field">
          <label htmlFor="company">Company / hotel name</label>
          <input id="company" value={company} onChange={(e) => setCompany(e.target.value)} required />
        </div>
        <div className="field">
          <label htmlFor="username">Admin username</label>
          <input id="username" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required />
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" required />
        </div>
        {error && <p style={{ color: "#f87171" }}>{error}</p>}
        <button type="submit" disabled={loading} style={{ width: "100%" }}>
          {loading ? "Creating…" : "Create account"}
        </button>
      </form>
      <p className="muted" style={{ marginTop: "1rem" }}>
        Already have an account? <Link href="/login">Sign in</Link>
      </p>
    </main>
  );
}
