# Edge Box Setup

Running detection at the customer's site instead of pulling their cameras to your server.

---

## 1. When to use this

Use an edge box when the site has more cameras than one VPS can analyse, when their internet upload cannot carry the video, or when the customer will not permit footage to leave the building.

| | Cloud pull | **Edge box** |
|---|---|---|
| Detection runs | Your VPS | The box at the site |
| Bandwidth | Every stream travels upstream | Only events and clips |
| Cameras per site | A handful | Dozens |
| Needs | Tailscale tunnel | A box on their LAN |
| Customer sees | Video leaving premises | Only alerts arriving |

The box reads the cameras **locally**, so no tunnel, no port forwarding and no inbound connection of any kind. It makes outbound HTTPS calls to your API and nothing more.

---

## 2. Hardware

| | Recommendation | Why |
|---|---|---|
| CPU | Any modern x86 mini PC | Torch installs cleanly; ARM is slower to build and slower to infer |
| RAM | **8 GB** | 4 GB works for one or two cameras, uncomfortably |
| Storage | 128 GB SSD | Local clips buffer until they are pushed |
| OS | Ubuntu Server 24.04 LTS | Matches your server, so commands are identical |

A Raspberry Pi 5 will run it, but installing PyTorch on ARM takes a long time and inference is roughly three times slower. For a customer deployment, spend the money on a small x86 box.

---

## 3. Install the dependencies

```bash
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip git libgl1 libglib2.0-0 ffmpeg
sudo mkdir -p /opt/smartcam && sudo chown "$USER" /opt/smartcam
cd /opt/smartcam
git clone https://github.com/Ponderosa-YRN/smartcam.git .
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
# CPU-only torch first: the CUDA build is several gigabytes and unusable here
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

That last step takes a while. If it dies with `Killed», the box is out of RAM — add swap:

```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

## 4. Write the site's config

The box keeps its own `config.json» describing the cameras it can see. These are **local** addresses — the same ones you would type into VLC while standing in their building.

```bash
nano /opt/smartcam/config.json
```

```json
{
  "sources": [
    {
      "id": "gate-1",
      "name": "Main gate",
      "uri": "rtsp://USER:PASS@192.168.1.15:554/Streaming/Channels/102",
      "enabled": true,
      "loop": true,
      "fast": false
    }
  ]
}
```

Keep `id» short and stable — it appears in the cloud as the camera identity. Use the **sub-stream** (`102» on a Hikvision NVR), not the main stream.

Test each URL on the box before going further:

```bash
.venv/bin/python -c "import cv2; c=cv2.VideoCapture('rtsp://USER:PASS@192.168.1.15:554/Streaming/Channels/102'); ok,f=c.read(); print('opened:', ok, f.shape if ok else None); c.release()"
```

---

## 5. Create the device token

In the cloud dashboard, signed in as an **admin**:

1. **Admin → Devices**
2. Select the customer's tenant — the device must belong to the tenant whose cameras it reports on
3. Name it after the site, e.g. `Acacia Hotel — gate box»
4. Create — **the token is shown once.** Copy it now

If it is lost, rotate it in the same panel and update the box. Rotating invalidates the old one immediately.

---

## 6. Run it

```bash
cd /opt/smartcam
.venv/bin/python edge_agent.py \
  --api-url https://agay.tech/smartapi \
  --token scd_1.YOUR_TOKEN_HERE \
  --config /opt/smartcam/config.json \
  --interval 15
```

The `/smartapi» suffix matters: Caddy routes that prefix to the API, and the client appends `/api/ingest/...» to whatever you give it.

You should see:

```
edge agent started: 1 source(s), pushing to https://agay.tech/smartapi
synced 3 records
```

Leave it running for a minute and confirm events appear in the cloud for that tenant. **Only then** make it permanent.

---

## 7. Make it survive a reboot

```bash
sudo tee /etc/systemd/system/smartcam-edge.service >/dev/null <<'EOF'
[Unit]
Description=SmartCam edge agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/smartcam
ExecStart=/opt/smartcam/.venv/bin/python edge_agent.py   --api-url https://agay.tech/smartapi   --token scd_1.YOUR_TOKEN_HERE   --config /opt/smartcam/config.json   --interval 15
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now smartcam-edge
sudo systemctl status smartcam-edge
```

Set the token with `sudo chmod 600 /etc/systemd/system/smartcam-edge.service» afterwards — the unit file holds a credential.

---

## 8. Verify

- [ ] `systemctl status smartcam-edge» shows **active (running)**
- [ ] `journalctl -u smartcam-edge -n 30» shows `synced N records»
- [ ] Events appear in the cloud dashboard under the right tenant and camera names
- [ ] Unplug the box's network for a minute, plug it back — events sync afterwards (the local database is a buffer, not just a cache)
- [ ] Reboot the box — the service comes back on its own

---

## 9. Do not also add these cameras to the cloud

If the same camera is configured on the box **and** as a source in the cloud, both analyse it and you get every event twice under two camera ids.

After the box is live, remove that camera from the cloud's Settings → Cameras.

---

## 10. Troubleshooting

| Symptom | Cause |
|---|---|
| `synced 0 records» forever | Cameras not producing events, or `uri» wrong — run the OpenCV check from §4 |
| `401» / `403» in the log | Token wrong, or the device was rotated/deleted |
| `event ingest failed» | Cannot reach your API — check `curl -sS https://agay.tech/smartapi/api/health» from the box |
| Events arrive without clips | Media upload failing; check disk space on the box |
| High CPU, few events | Main stream instead of sub-stream, or too many cameras for the box |
| Service restarts in a loop | Read `journalctl -u smartcam-edge -n 100» — usually a bad `config.json» |

---

## 11. Security notes

- The box makes **only outbound** connections. Block all inbound traffic on the customer router; nothing needs to reach it.
- The device token is a credential. It lives in the systemd unit — keep that file `600», and rotate the token if the box is lost or stolen.
- Deleting the device in **Admin → Devices** revokes it immediately; the box's syncs will start failing, which is the intended behaviour.
- The local `data/» directory holds clips of the customer's premises. Treat the box as sensitive hardware, and wipe it if it is decommissioned.
