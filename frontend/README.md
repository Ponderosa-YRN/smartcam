# SmartCam frontend (Next.js)

Web app for the SmartCam API (React + Next.js App Router + TypeScript).

## Prerequisites
- Node 18+ (tested on Node 24)
- The SmartCam API running (from the repo root): .venv/Scripts/python run_api.py

## Setup
1. npm install
2. copy .env.local.example to .env.local and set NEXT_PUBLIC_API_URL (default http://localhost:8000)
3. npm run dev  ->  http://localhost:3000

## Notes
- Auth token is stored in localStorage (v1). Switch to an httpOnly cookie via a
  Next.js server route as a hardening step.
- The API allows CORS via SMART_CAM_CORS_ORIGINS (default "*").
- This is a walking skeleton: login, user info, recent events, and a live
  WebSocket feed. Live view, alerts, search, and analytics pages come next.
