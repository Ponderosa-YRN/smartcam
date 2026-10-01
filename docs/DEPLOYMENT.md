# SmartCam - live deployment

The whole product runs on one Hostinger VPS behind one domain. No PaaS, no second
origin, no CORS.

    Internet
        |
        v
    https://agay.tech                            VPS 187.7.27.37
        |
        +-- container "caddy"  (host network, TLS via Let's Encrypt, auto-renewed)
        |       |
        |       +-- API paths ----------> 127.0.0.1:8000   container "smartcam"     (FastAPI)
        |       |
        |       +-- everything else ----> 127.0.0.1:3000   container "smartcam-web" (Next.js)
        |
        +-- Docker volume mounted at /app/data   (SQLite DB, clips, thumbnails)

## Routing - /root/Caddyfile

| Path | Destination |
| --- | --- |
| `/smartapi/*` (prefix stripped) | FastAPI |
| `/auth/*`, `/tenants`, `/tenants/*`, `/invites/*`, `/plans`, `/device/*` | FastAPI |
| `/api/*`, `/ws/*`, `/openapi.json`, `/docs*`, `/redoc` | FastAPI |
| everything else (`/`, `/login`, `/_next/*`, ...) | Next.js dashboard |

The dashboard calls its own origin under `/smartapi`, so the browser never makes a
cross-origin request, and `/ws/*` gives live video a same-origin WebSocket.

## Deploying a dashboard change

    # on your machine
    git push

    # on the VPS
    bash /root/smartcam/scripts/deploy_web.sh

That pulls, rebuilds the image, restarts the container and health-checks it. It never
touches the Caddyfile.

## Deploying an API change

No script for this yet. It means rebuilding the API image and recreating the `smartcam`
container while preserving its env vars and its `/app/data` volume.
`scripts/harden_api_port.sh` demonstrates the safe capture-and-recreate pattern
(inspect -> reuse exact env/volumes -> health check -> roll back on failure).

## Changing routing

    cp -a /root/Caddyfile /root/Caddyfile.bak
    nano /root/Caddyfile
    docker exec caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
    docker restart caddy

Always validate before restarting: a broken Caddyfile takes down the dashboard *and*
the API.

## Containers

| Container | Bound to | Purpose |
| --- | --- | --- |
| `caddy` | 80, 443 (host network) | TLS termination + routing |
| `smartcam` | 127.0.0.1:8000 | FastAPI control plane |
| `smartcam-web` | 127.0.0.1:3000 | Next.js dashboard |

Both app ports are loopback-only on purpose - nothing but Caddy should reach them.

## Older documents

`COOLIFY_DEPLOY.md`, `HOSTINGER_SETUP.md` and `HOSTING_PLAN.md` describe earlier plans
(Coolify, Hetzner, Fly.io, Vercel). They are kept for history and are **not** the live setup.
