"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { getToken } from "@/lib/api";

const CTA = {
  display: "inline-block",
  padding: ".55rem 1.05rem",
  borderRadius: "var(--r-sm)",
  background: "var(--brand)",
  color: "#fff",
  textDecoration: "none",
  fontSize: ".92rem",
  fontWeight: 500,
} as const;

const CTA_GHOST = { ...CTA, background: "transparent", border: "1px solid var(--border-strong)", color: "var(--text)" } as const;

/**
 * The public page. Signed-in users skip it; everyone else sees what this is before being
 * asked to sign in. Deliberately plain: no customer counts, no percentages, no badges we
 * have not earned — every claim here describes something the product actually does.
 */
export default function Home() {
  const router = useRouter();

  // Render the page first and redirect afterwards: a page that returns null until hydration
  // is invisible to a crawler and flashes empty on a slow connection. The cost is that a
  // signed-in user sees this page for a moment before being sent to the dashboard.
  useEffect(() => {
    if (getToken()) router.replace("/dashboard");
  }, [router]);

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: "3rem 1.5rem 4rem" }}>
      <header className="row" style={{ justifyContent: "space-between", marginBottom: "4rem" }}>
        <strong style={{ fontSize: "1.05rem", letterSpacing: "-.01em" }}>SmartCam</strong>
        <Link href="/login" style={CTA_GHOST}>
          Sign in
        </Link>
      </header>

      <h1 style={{ fontSize: "2.3rem", lineHeight: 1.15, letterSpacing: "-.03em", maxWidth: 640 }}>
        Know what happened. Then show the clip.
      </h1>
      <p className="muted" style={{ fontSize: "1.05rem", lineHeight: 1.6, maxWidth: 620, marginTop: "1rem" }}>
        SmartCam runs on the cameras your hotel or estate already has. It turns what they
        record into a searchable record — alerts, clips and times — so answering "what
        happened last night" takes a minute instead of an hour of scrubbing.
      </p>

      <div className="row" style={{ margin: "2rem 0 4rem" }}>
        <Link href="/login" style={CTA}>
          Sign in
        </Link>
        <span className="muted" style={{ fontSize: ".88rem" }}>
          Accounts are created by invitation.
        </span>
      </div>

      <div className="grid" style={{ marginBottom: "4rem" }}>
        <div className="card">
          <h3>Detects</h3>
          <p className="muted" style={{ margin: 0, lineHeight: 1.6 }}>
            People, vehicles, loitering, intrusion, queues and car parks. Detection runs on
            your own hardware — the footage does not leave it.
          </p>
        </div>
        <div className="card">
          <h3>Alerts</h3>
          <p className="muted" style={{ margin: 0, lineHeight: 1.6 }}>
            A detection becomes an event with a clip and a thumbnail. Your staff acknowledges,
            resolves, assigns or escalates it — a duty guard can act without being able to
            reconfigure anything.
          </p>
        </div>
        <div className="card">
          <h3>Answers</h3>
          <p className="muted" style={{ margin: 0, lineHeight: 1.6 }}>
            Search by what happened, or ask the co-pilot in plain language. Every answer cites
            the event number and the time, so you can open the clip and check it yourself.
          </p>
        </div>
      </div>

      <h2 style={{ fontSize: "1.25rem", marginBottom: "1rem" }}>Built for two kinds of site</h2>
      <div className="grid" style={{ marginBottom: "4rem" }}>
        <div className="card">
          <h3>Hotels</h3>
          <p className="muted" style={{ margin: 0, lineHeight: 1.6 }}>
            Guest areas, car parks, staff entrances and after-hours coverage. Settle a guest
            dispute, or find out who was at the service door at 2am.
          </p>
        </div>
        <div className="card">
          <h3>Gated estates</h3>
          <p className="muted" style={{ margin: 0, lineHeight: 1.6 }}>
            Perimeter, gatehouse and shared facilities. Unknown vehicles, loitering at the
            fence, and a record you can hand to the residents' association.
          </p>
        </div>
      </div>

      <h2 style={{ fontSize: "1.25rem", marginBottom: "1rem" }}>What it does</h2>
      <div className="card" style={{ marginBottom: "4rem" }}>
        <ul className="muted" style={{ lineHeight: 1.9, margin: 0, paddingLeft: "1.2rem" }}>
          <li>Live view from every camera, with a low-latency mode</li>
          <li>Detection events with a clip, a thumbnail and an AI summary</li>
          <li>Zones and rules per camera — loitering, intrusion, queueing, parking capacity</li>
          <li>Licence plate reading on vehicles entering car parks</li>
          <li>Face recognition and cross-camera re-identification</li>
          <li>Occupancy counts and history</li>
          <li>Per-site retention, audit logging, and roles for admin, manager, security and viewer</li>
          <li>One deployment serving several hotels or estates, isolated from each other</li>
        </ul>
      </div>

      <h2 style={{ fontSize: "1.25rem", marginBottom: "1rem" }}>What we will not pretend</h2>
      <div className="card" style={{ marginBottom: "4rem" }}>
        <ul className="muted" style={{ lineHeight: 1.9, margin: 0, paddingLeft: "1.2rem" }}>
          <li>If a camera was offline, the system says so instead of implying coverage it did not have.</li>
          <li>"No events recorded" is not the same as "nothing happened", and it is not reported that way.</li>
          <li>There is no public sign-up. Access is by invitation from whoever manages your site.</li>
        </ul>
      </div>

      <footer className="row" style={{ justifyContent: "space-between", borderTop: "1px solid var(--border)", paddingTop: "1.5rem" }}>
        <span className="muted" style={{ fontSize: ".85rem" }}>SmartCam — access by invitation</span>
        <Link href="/login" className="muted" style={{ fontSize: ".85rem" }}>Sign in</Link>
      </footer>
    </div>
  );
}
