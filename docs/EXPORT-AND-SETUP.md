# Exporting the workspace to a new system

**Short version: the git repository *is* the export.** Everything needed to run SmartCam is
committed and pushed. The 2.8 GB sitting in your working directory is build output you should not
carry across.

---

## 1. What is where

| Thing | In git? | Action on the new machine |
|---|---|---|
| All source (backend, frontend, scripts, docs) | ✅ | Clone it |
| Model weights — `yolov8n.onnx`, `yolov8n.pt`, `yolov8n-pose.pt` (26 MB) | ✅ | Comes with the clone |
| Dockerfiles, compose file, deploy scripts | ✅ | Clip |
| `.venv/` — 2.5 GB | ❌ ignored | **Rebuild.** Carrying a virtualenv across machines does not work |
| `frontend/node_modules/` — 332 MB | ❌ ignored | **Rebuild** with `npm install` |
| `frontend/.next/` | ❌ ignored | Rebuild |
| `data/` — 64 MB local dev database and clips | ❌ ignored | Optional. Copy only if you want that test data |
| `config.json` (API keys, TURN credentials) | ❌ ignored | **Re-provision.** See §5 |
| `.security-audit/` | ❌ ignored | Copy if you want the audit run |
| `SmartCam-portable.zip`, `torch_install.log` | ❌ ignored | Junk. Leave behind |
| `CANADIAN-HOUSING-CARE-PROMPT.md` | ❌ **untracked** | Belongs to the other project — move it there, do not carry it into this one |

There is no `config.json` in this working directory, so **no secrets live here**. That is
deliberate and worth keeping.

---

## 2. Option A — clone (normal case)

The repository is private, so the new machine needs a GitHub credential first: a personal access
token, or an SSH key added to the account.

```bash
git clone https://github.com/Ponderosa-YRN/smartcam.git
cd smartcam
git log --oneline -1        # expect 490efc6
```

## 3. Option B — offline bundle (no network on the new machine)

A bundle is the whole history in one file. It does not duplicate build output, which is the mistake
a zip makes.

```bash
# on this machine
git bundle create smartcam.bundle --all

# on the new system
git clone smartcam.bundle smartcam
cd smartcam
git remote set-url origin https://github.com/Ponderosa-YRN/smartcam.git
```

---

## 4. Set up the new machine

**Prerequisites:** Python 3.11+, Node 20+, Docker (for the production path), git.

**Backend:**

```bash
python3 -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install --upgrade pip
# CPU-only torch first - the CUDA build is several GB and unusable without a GPU
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

On Linux also install the OpenCV system libraries:

```bash
sudo apt-get install -y libgl1 libglib2.0-0 ffmpeg
```

**Frontend:**

```bash
cd frontend
npm install
cd ..
```

**Verify before going further:**

```bash
python -m pytest tests -q          # expect 74 passing
python -c "import smartcam.api as a; print(len(a.app.routes))"   # expect 80
cd frontend && npx tsc --noEmit && cd ..
```

---

## 5. Secrets to re-provision

Nothing secret is in the repository. These have to exist on the new system:

| Secret | Where it belongs | Notes |
|---|---|---|
| `SMART_CAM_TOKEN_SECRET` | env or `data/.token_secret` | Losing it invalidates every token; devices need re-enrolment |
| `config.json` | `data/` (mounted volume) | Contains VLM/S3/TURN credentials. **Copy it deliberately or re-enter it in Settings** — never commit it |
| `COPILOT_API_KEY` / `COPILOT_BASE_URL` / `COPILOT_MODEL` | env | Co-pilot provider |
| `SMART_CAM_PLATFORM_KEY` | env | Required to change a tenant plan |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | `/root/.smartcam-alert.env`, mode 600 | Disk and site alerts |

**If the new machine is also the new server**, the live `config.json` is inside the container, not
here. Take it from the running system:

```bash
docker cp smartcam:/app/data/config.json ./config.json
```

Treat that file as a credential: it holds provider keys.

---

## 6. If you are migrating the running deployment, not just the code

Code is the easy half. The data lives on the VPS.

**On the old server:**

```bash
cd /root/smartcam && BACKUP_MEDIA=1 ./scripts/backup.sh
```

That produces `/root/smartcam-backups/smartcam-<timestamp>.tar.gz` containing the database, config,
audit log and media. Prove it before moving it:

```bash
./scripts/restore.sh --check /root/smartcam-backups/smartcam-<timestamp>.tar.gz
```

**On the new server:**

```bash
# after cloning the repo and completing §4
./scripts/restore.sh /root/smartcam-backups/smartcam-<timestamp>.tar.gz
```

The restore stops the container, replaces the database and config, restarts, and health-checks.

**Do not overlook:** DNS for `agay.tech`, the firewall rules (and `netfilter-persistent save` so they
survive a reboot), the cron jobs (backups, disk check, site check), and the Tailscale tunnel if any
camera is reached that way.

---

## 7. What not to copy

| Do not copy | Why |
|---|---|
| `.venv` | Absolute paths inside it break. Rebuild in under five minutes |
| `node_modules` | Platform-specific binaries; `npm install` is faster than debugging it |
| `.next` | Build output |
| `SmartCam-portable.zip`, `torch_install.log` | Neither is part of the product |
| `CANADIAN-HOUSING-CARE-PROMPT.md` | Belongs to the other project |

---

## 8. First run on the new machine

```bash
python run_api.py --port 8000
cd frontend && npm run dev
```

Then `http://localhost:3000`. If no users exist, create one:

```bash
python scripts/create_user.py --username admin --password 'something-long' --role admin
```

Delete any test data first if you copied `data/` from a machine that had real
tenants in it.
