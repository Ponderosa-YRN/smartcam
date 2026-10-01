# SmartCam — Hostinger VPS Setup (step by step)

> **Historical — not the live setup.** The dashboard no longer runs on Vercel; the whole
> app is served from this VPS on one origin. See [DEPLOYMENT.md](DEPLOYMENT.md).

Deploy the SmartCam backend on your Hostinger VPS, using Coolify (recommended —
it gives you a UI, auto-HTTPS, and easy Postgres later) or plain Docker.

## 0. What you need
- Your Hostinger VPS IP + root password (hPanel -> VPS -> SSH access).
- Your SmartCam code pushed to a GitHub repo.
- ~30-45 minutes.

## 1. SSH into the VPS

Open PowerShell on your computer:

    ssh root@<your-vps-ip>

Type yes to the fingerprint prompt, then enter the root password.

## 2. Install Docker

    curl -fsSL https://get.docker.com | sh

Verify:

    docker --version

## 3. Install Coolify

    curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash

Wait 2-5 minutes. At the end it prints a URL and a temporary password. Open
http://<your-vps-ip>:8000 in a browser and finish the setup (create your Coolify
admin user).

## 4. Deploy SmartCam (build from your GitHub repo)

In the Coolify web UI:

1. Projects -> + Add -> New Project -> name it "SmartCam".
2. Open the project -> + Add -> Application -> "Public Repository" (GitHub).
3. Connect your GitHub account, pick your SmartCam repo and the "main" branch.
4. Build Pack: Dockerfile (it auto-detects the Dockerfile).
5. Ports Exposes: 8000.
6. Persistent Storage: add a volume and mount it at /app/data.
7. Domains: accept the sslip.io preview URL for now.
8. Add the environment variables from step 5.
9. Click Deploy. The first build downloads PyTorch, so it takes 5-15 minutes.

## 5. Environment variables

Generate a token secret (run anywhere you have Python):

    python -c "import secrets; print(secrets.token_hex(32))"

On the resource, under Environment Variables, add:

    SMART_CAM_ADMIN_PASSWORD = <your-admin-password>
    SMART_CAM_TOKEN_SECRET  = <the-hex-you-just-generated>
    SMART_CAM_CORS_ORIGINS  = *

## 6. Verify it is running

- Coolify -> resource -> Runtime Logs should show "SmartCam API started ...".
- From your computer:

    curl http://<the-sslip.io-url>/api/health

  You should get back {"status":"ok","service":"smartcam"}.

NOTE: do NOT type http://<ip>:8000 for the app — Coolify itself uses 8000. Use the
sslip.io URL (or your domain after step 8).

## 7. Point the Vercel frontend at it

Vercel -> project -> Settings -> Environment Variables:

    NEXT_PUBLIC_API_URL = http://<the-sslip.io-url>

(Change to https://api.<your-domain> after step 8.)

## 8. Real domain + HTTPS (recommended)

1. At your DNS provider, add an A record: api.yourdomain.com -> <your-vps-ip>.
2. Coolify -> resource -> Domains -> replace the sslip.io URL with api.yourdomain.com
   (Coolify auto-issues a Let's Encrypt certificate).
3. Update Vercel: NEXT_PUBLIC_API_URL = https://api.yourdomain.com.

## 9. Hostinger firewall

In hPanel -> VPS -> Firewall, make sure ports 80, 443, and 8000 are allowed so
Coolify and your app are reachable.

## Alternative: plain Docker (no Coolify)

If you prefer no extra layer:

    curl -fsSL https://get.docker.com | sh
    git clone https://github.com/<you>/<repo>.git smartcam
    cd smartcam
    # edit docker-compose.yml: comment the image: line, uncomment "build: ."
    docker compose up -d --build
    curl http://localhost:8000/api/health

## Troubleshooting

| Problem | Fix |
| --- | --- |
| Can't reach the app at IP:8000 | Coolify uses 8000. Use the sslip.io URL or your domain. |
| Build fails downloading torch | Click Redeploy to retry (network hiccup). |
| "Image pull access denied" | You used the GHCR image path; it is private. Use the Git-repo (build) path instead, or make the GitHub package public. |
| Login says 401 | Wrong admin password (what you set in SMART_CAM_ADMIN_PASSWORD). |
| Frontend "failed to fetch" | API URL wrong/unreachable, or CORS. Use HTTPS (step 8) and set SMART_CAM_CORS_ORIGINS. |
