# SmartCam — Step-by-Step Deployment on Coolify + Hetzner

A full, ordered walkthrough to get the SmartCam backend running on your own VPS.
Follow every step in order. Budget ~45 minutes + the first build (~5-15 min).

What we are doing: buy a Hetzner VPS -> install Coolify on it -> deploy the
SmartCam backend (built from your GitHub repo) -> point the frontend at it ->
connect hotels via the edge agent.

---

## Part 0 — Before you start (checklist)

- [ ] A debit/credit card (Hetzner requires one to create a server).
- [ ] Your SmartCam code pushed to a GitHub repository (Coolify clones it).
- [ ] Your GitHub username.
- [ ] A way to SSH (Windows 10/11 has ssh built into PowerShell).

---

## Part 1 — Buy the Hetzner VPS (CX32, 4 GB)

1. Go to https://console.hetzner.cloud and create an account (verify email + add a
   card — this is how you pay the ~EUR 6/mo).
2. Click "Create a Project" and name it (e.g. "SmartCam").
3. Inside the project, click "Add Server".
4. Choose:
   - Location: Nuremberg (NBG) or Falkenstein (FSN) — both in Germany, good for Nigeria.
   - Image: Ubuntu 22.04 (or 24.04).
   - Type: CX32 (4 GB RAM, 2 vCPU) — this is the one.
   - Networking: keep IPv4 enabled.
5. Authentication: choose "SSH key" (recommended) OR "Password" (root).
   - If SSH key: paste your public key (see the box below if you don't have one).
   - If password: Hetzner emails you a root password.
6. Give it a name, click "Create & Buy now".
7. Note the server's IPv4 address — you will use it everywhere below.

How to make an SSH key on Windows (optional, if you picked SSH key):

    ssh-keygen -t ed25519
    # then print your public key:
    cat ~/.ssh/id_ed25519.pub

---

## Part 2 — SSH into the VPS

Open PowerShell (not from the SmartCam folder; anywhere is fine):

    ssh root@<your-vps-ip>

- First time it asks "Are you sure you want to continue connecting?" — type yes.
- Enter your root password (or it uses your SSH key automatically).

Once you see a root prompt, update the server:

    apt update && apt upgrade -y

---

## Part 3 — Install Coolify

Run this one command on the VPS:

    curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash

It installs Docker + Coolify. Wait ~2-5 minutes. At the end it prints a URL and
a temporary password — copy both.

Open a browser and go to:

    http://<your-vps-ip>:8000

Finish the setup wizard (create your Coolify admin user). You can skip the domain
step for now.

IMPORTANT: Coolify itself runs on port 8000. That is why SmartCam is reached via
a domain/subdomain later (Part 9), NOT by typing the raw IP + :8000.

---

## Part 4 — Push your code to GitHub (so Coolify can build it)

If you have not pushed yet, from the SmartCam project folder:

    git init
    git add .
    git commit -m "Deploy SmartCam"
    git branch -M main
    git remote add origin https://github.com/<your-username>/<repo>.git
    git push -u origin main

Optional but useful: wait for the GitHub Actions workflow "Docker build + smoke
test" to finish green — that confirms the Dockerfile builds correctly before you
spend time in Coolify.

---

## Part 5 — Deploy the backend in Coolify

1. In Coolify, go to "Projects" -> "+ Add" -> "New Project" -> name it "SmartCam".
2. Open the project -> "+ Add" -> "Application" -> choose "Public Repository"
   (GitHub). (Button labels vary slightly between Coolify versions.)
3. Connect your GitHub account and select your SmartCam repo + the "main" branch.
4. Build Pack: Dockerfile (it auto-detects the Dockerfile in the repo).
5. Ports Exposes: 8000.
6. Persistent Storage: add a volume and mount it at /app/data.
   (This is where clips, thumbnails, and the database live.)
7. Domains: Coolify suggests something like <app>.<your-ip>.sslip.io — accept it
   for now; you will set a real domain in Part 9.
8. Add the environment variables from Part 6.
9. Click "Deploy".

The first build downloads PyTorch + dependencies, so it takes 5-15 minutes. Watch
the "Build Logs" then "Runtime Logs".

---

## Part 6 — Set the environment variables (required)

Generate a random token secret (run anywhere you have Python):

    python -c "import secrets; print(secrets.token_hex(32))"

On the Coolify resource, under Environment Variables, add:

    SMART_CAM_ADMIN_PASSWORD = <your-admin-password>
    SMART_CAM_TOKEN_SECRET  = <the-hex-you-just-generated>
    SMART_CAM_CORS_ORIGINS  = *

Optional extras (all documented in .env.example):

    DATABASE_URL            (only if you later use Postgres)
    SMART_CAM_S3_BUCKET     (only if you use S3/R2 for clips)
    SMART_CAM_TURN_URL      (only if edge cameras are behind symmetric NAT)
    SMART_CAM_OPENAI_API_KEY (only for AI event summaries)
    SMART_CAM_NOTIFY_URL    (only for push notifications)

---

## Part 7 — Verify it is running

1. In Coolify, open the resource and watch Runtime Logs — it should show
   "SmartCam API started ..." with no tracebacks.
2. From your own machine (PowerShell):

    curl http://<the-sslip.io-or-your-domain>/api/health

   You should get back:

    {"status":"ok","service":"smartcam"}

3. Open the auto-generated API docs in a browser:

    http://<the-sslip.io-or-your-domain>/docs

If the health check does not respond, see Part 11.

---

## Part 8 — Point the Vercel frontend at the API

1. In Vercel, open your frontend project -> Settings -> Environment Variables.
2. Add:

    NEXT_PUBLIC_API_URL = http://<the-sslip.io-or-your-domain>

   (Change this to https://api.<your-domain> after Part 9.)
3. Redeploy the frontend (Vercel redeploys automatically when you change env vars,
   or push a commit).

Note: if the frontend is https and the API is http, browsers block the request
("mixed content"). That is why Part 9 (HTTPS on the API) is recommended.

---

## Part 9 — Put a real domain + HTTPS on the API (recommended)

1. Buy a domain (or use a subdomain like api.yourdomain.com).
2. At your DNS provider, create an A record:
   - Name: api  (or @ for the root)
   - Value: <your-vps-ip>
3. In Coolify, on the SmartCam resource -> Domains -> replace the sslip.io URL with
   api.yourdomain.com. Coolify automatically requests a Let's Encrypt certificate
   (HTTPS).
4. Update the Vercel env var:

    NEXT_PUBLIC_API_URL = https://api.yourdomain.com

---

## Part 10 — Connect the first hotel (edge)

1. Log in to the frontend with the admin username + the password you set in Part 6.
2. Go to Admin -> Edge devices -> pick a tenant -> "Provision device" -> copy the
   token (it is shown only once).
3. On the hotel's machine (which runs the edge agent):

    .venv\Scripts\python.exe edge_agent.py --api-url https://api.yourdomain.com --token scd_<tenant>.<signed>

Events + occupancy from that hotel then appear in the cloud tenant's Events and
Analytics screens.

---

## Part 11 — Troubleshooting

| Problem | Fix |
| --- | --- |
| Health check times out | Open Runtime Logs in Coolify. Common causes: missing model file, or VPS RAM too low (use CX32 = 4 GB). |
| Build fails downloading torch | Network hiccup — click "Redeploy" to retry. |
| "Image pull access denied" (only if you used the GHCR image path) | GHCR packages are PRIVATE by default. Make the package public (GitHub -> repo -> Packages -> Package Settings -> Change visibility -> Public), or add a GitHub token to Coolify. |
| Can't reach the app by typing IP:8000 | Coolify uses 8000 for its own UI. Use the sslip.io URL or your domain instead. |
| Frontend says "failed to fetch" | The API URL is wrong/unreachable, or CORS. Set SMART_CAM_CORS_ORIGINS to your frontend origin, and use https on the API (Part 9). |
| Login says 401 | Wrong admin password — it is whatever you set in SMART_CAM_ADMIN_PASSWORD on first boot. |

---

## Appendix — alternative deploy methods

- Docker Image (GHCR): faster redeploys, but you must make the GitHub package
  public or give Coolify a token.
- Docker Compose: use docker-compose.yml in the repo (replace your-username in the
  image name). Good if you prefer a single declarative file.

---

## What I cannot do for you

I cannot buy the VPS, run the Coolify installer, or deploy from this sandbox —
those need your accounts, SSH access, and a real server. Everything up to here
(the Dockerfile, CI, compose file, env template, and this guide) is ready; the
steps above are executed by you on the box.
