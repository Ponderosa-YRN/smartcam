# SmartCam — Deployment

Three ways to run it in production.

## 1. Docker (recommended)

    docker compose up -d --build

Open http://localhost:8501 for the dashboard.

To run the headless API instead, edit docker-compose.yml and set:

    command: ["python", "run_api.py", "--port", "8000"]

## 2. Linux systemd (headless API)

    # install
    sudo mkdir -p /opt/smartcam
    sudo cp -r . /opt/smartcam
    cd /opt/smartcam
    sudo python3 -m venv .venv
    sudo .venv/bin/pip install -r requirements.txt

    # service
    sudo cp deploy/smartcam.service /etc/systemd/system/smartcam.service
    sudo systemctl daemon-reload
    sudo systemctl enable --now smartcam
    sudo systemctl status smartcam

    # logs
    journalctl -u smartcam -f

## 3. Windows (NSSM) — run the API or dashboard as a service

Install NSSM (https://nssm.cc), then from an admin prompt:

    nssm install SmartCam "C:\path\to\SmartCam\.venv\Scripts\python.exe" "run_api.py --port 8000"
    nssm set SmartCam AppDirectory "C:\path\to\SmartCam"
    nssm set SmartCam AppEnvironmentExtra SMART_CAM_CONFIG=C:\path\to\SmartCam\config.json
    nssm start SmartCam

Or run the dashboard as a service:

    nssm install SmartCamDashboard "C:\path\to\SmartCam\.venv\Scripts\python.exe" "-m streamlit run app.py --server.headless=true --server.port=8501"

## Notes

- The dashboard embeds the pipeline; the API is a separate headless service.
  Run ONE of them against a given config.json/data dir (they both write to the
  same SQLite database).
- For GPU inference, build the image FROM nvidia/cuda base and install the
  CUDA torch wheel.
