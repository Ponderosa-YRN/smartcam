"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { getToken } from "@/lib/api";

interface Turn {
  who: "you" | "vera";
  text: string;
  evidence?: number[];
}

const SUGGESTIONS = [
  "What happened in the last 24 hours?",
  "Which cameras are offline?",
  "What is still unhandled?",
  "How busy was it today?",
];

export default function Copilot({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const bodyRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
  }, [turns, busy]);

  async function ask(question: string) {
    const q = question.trim();
    if (!q || busy) return;
    setInput("");
    setTurns((prev) => [...prev, { who: "you", text: q }]);
    setBusy(true);
    try {
      const res = await fetch("/copilot", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer " + (getToken() ?? ""),
        },
        body: JSON.stringify({ question: q }),
      });
      const data = (await res.json()) as {
        answer?: string;
        error?: string;
        evidence?: number[];
      };
      setTurns((prev) => [
        ...prev,
        {
          who: "vera",
          text: data.answer || data.error || "I have no answer for that.",
          evidence: data.evidence,
        },
      ]);
    } catch {
      setTurns((prev) => [...prev, { who: "vera", text: "I could not reach the server." }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className={"copilot" + (open ? " open" : "")} aria-hidden={!open}>
      <header className="copilot-head">
        <span className="mark" style={{ width: 24, height: 24, fontSize: 12 }}>
          ◉
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <strong>Vera</strong>
          <div className="muted" style={{ fontSize: ".76rem" }}>
            Duty officer
          </div>
        </div>
        <button className="secondary btn-sm" onClick={onClose}>
          Close
        </button>
      </header>

      <div className="copilot-body" ref={bodyRef}>
        {turns.length === 0 && (
          <>
            <p className="muted" style={{ margin: 0, fontSize: ".88rem" }}>
              I report what the cameras recorded — and I will tell you what I could not see.
            </p>
            <div className="row" style={{ gap: ".4rem", margin: 0 }}>
              {SUGGESTIONS.map((s) => (
                <button key={s} className="chip" onClick={() => ask(s)}>
                  {s}
                </button>
              ))}
            </div>
          </>
        )}

        {turns.map((turn, i) => (
          <div className={"turn " + turn.who} key={i}>
            <div className="who">{turn.who === "you" ? "You" : "Vera"}</div>
            <div className="bubble">{turn.text}</div>
            {turn.evidence && turn.evidence.length > 0 && (
              <div className="row" style={{ gap: ".3rem", margin: ".45rem 0 0" }}>
                {turn.evidence.slice(0, 8).map((id) => (
                  <Link key={id} href="/events" className="chip" onClick={onClose}>
                    Event #{id}
                  </Link>
                ))}
              </div>
            )}
          </div>
        ))}

        {busy && <div className="muted" style={{ fontSize: ".85rem" }}>Checking the logs…</div>}
      </div>

      <form
        className="copilot-foot"
        onSubmit={(e) => {
          e.preventDefault();
          ask(input);
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about anything the cameras saw…"
        />
        <button type="submit" disabled={busy || !input.trim()}>
          Ask
        </button>
      </form>
    </aside>
  );
}
