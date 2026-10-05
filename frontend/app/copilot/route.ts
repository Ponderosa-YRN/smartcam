import { NextResponse } from "next/server";
import { ask } from "@/lib/copilot";

// Deliberately NOT under /api: Caddy routes /api/* to the Python backend.
// This path falls through to the Next.js app, so it needs no Caddy change.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const token = (req.headers.get("authorization") || "").replace(/^Bearer\s+/i, "").trim();
  if (!token) {
    return NextResponse.json({ error: "Not signed in." }, { status: 401 });
  }

  let question = "";
  try {
    const body = (await req.json()) as { question?: string };
    question = (body.question || "").trim();
  } catch {
    return NextResponse.json({ error: "Bad request." }, { status: 400 });
  }
  if (!question) {
    return NextResponse.json({ error: "Ask a question." }, { status: 400 });
  }

  try {
    return NextResponse.json(await ask(question, token));
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "Vera failed to answer." },
      { status: 500 }
    );
  }
}
