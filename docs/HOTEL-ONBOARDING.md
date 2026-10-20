# Hotel Onboarding — Field Directive

For taking SmartCam live at one hotel. Written to be used on site, in order.

---

## 0. Decide the architecture first

There are two ways a hotel's cameras reach SmartCam. Pick one before you touch a camera.

| | **A — Cloud pull** | **B — Edge box** |
|---|---|---|
| Where detection runs | Your VPS | A machine at the hotel |
| What the hotel needs | Their NVR reachable from your VPS | A small always-on computer with Python |
| Bandwidth | Every stream travels to your VPS | Only events and clips travel |
| Scales to | A handful of cameras | Dozens |
| Setup time | ~1 hour | Half a day, plus hardware |
| **Use this tomorrow** | ✅ | Later, when a site exceeds what the VPS can do |

**Tomorrow: Path A.** It needs no hardware beyond a laptop, and it proves the value fast.

---

## 1. Before you leave

Ask the hotel, in advance:

- NVR or camera **brand and model**, and roughly how many cameras
- Who holds the **NVR password**, and will they create a **dedicated read-only account** for SmartCam
- Whether they will permit **remote access** to the NVR
- Whether they understand that **video will leave the premises** and be processed and stored on your server

Bring a laptop, an ethernet cable, and a phone hotspot as a fallback.

**Do not use the hotel's admin NVR password.** Ask them to create a viewer account for you. If you use admin and something goes wrong, you own it.

---

## 2. On site — collect these facts

| Fact | Example | Notes |
|---|---|---|
| NVR local IP | `192.168.1.15` | From the NVR network menu |
| RTSP port | `554` | Default; sometimes 10554 |
| Web/HTTP port | `80` or `8000` | For logging into the NVR UI |
| Channels in use | 1–12 | You do not need to add all of them |
| Camera names | Gate, Lobby, Car park | These appear in the dashboard |
| Credentials | `smartcam / ••••` | The read-only account |

Write channel numbers down next to the camera names. Getting this wrong means the right alert arrives labelled with the wrong place, which erodes trust faster than a missing alert.

---

## 3. Build the RTSP URL

Formats differ by vendor. These are the common ones — **verify in VLC before going further** (Media → Open Network Stream).

| Vendor | Main stream | Notes |
|---|---|---|
| Hikvision | `rtsp://user:pass@IP:554/Streaming/Channels/101` | `102` is the sub-stream for the same camera. `201` = channel 2 |
| Dahua | `rtsp://user:pass@IP:554/cam/realmonitor?channel=1&subtype=0` | `subtype=1` is the sub-stream |
| Uniview | `rtsp://user:pass@IP:554/media/video1` | `video2` for the next channel |
| Axis | `rtsp://user:pass@IP/axis-media/media.amp` | |
| Generic / ONVIF | Discover with ONVIF Device Manager | If it lists an RTSP path, use it |

**Use the sub-stream, not the main stream.** A 4K main stream costs ten times the CPU and bandwidth and detects no better at this range. If the sub-stream is 704×576 or 1280×720, that is ideal.

Beware the `&` in Dahua URLs — in a shell, quote the whole URL.

---

## 4. Make the NVR reachable from your VPS

The NVR sits on a private network your server cannot see. Two options:

**Do not port-forward the NVR.** Home and hotel connections are frequently behind CGNAT, it exposes the NVR to the internet, and it is the reason devices get compromised.

**Use Tailscale** — a private mesh network, free for this scale, no router changes.

1. Install Tailscale on the VPS and join your tailnet
2. Install Tailscale on a machine at the hotel that stays powered on, and join the same tailnet
3. From the VPS, `ping <hotel-machine-tailscale-ip>` must succeed

The hotel machine then acts as a bridge to its LAN. For tomorrow a laptop is acceptable **as a demo**, but say plainly that it is temporary — a customer deployment needs a small always-on box.

> Check this before you touch the NVR. If the tunnel does not work, nothing after it will, and you will waste the visit.

---

## 5. Add the camera in SmartCam

1. Sign in as an **admin** or **manager** (a `viewer` or `security` account cannot add cameras)
2. **Settings → Cameras → add**
3. Paste the RTSP URL, using the NVR's address **as seen from the tunnel**
4. Save, then open **Live** and confirm a picture

If the picture is black or green, the stream path is wrong — go back to VLC and confirm the exact URL that worked there.

---

## 6. Verify before you leave

Do not leave until all of these are true:

- [ ] Live view shows the camera, and the image moves
- [ ] The camera reports **running** in Settings
- [ ] Walk in front of one camera — an event appears with a clip
- [ ] The event appears within a few seconds
- [ ] `docker stats --no-stream` on your VPS shows CPU stable, not climbing
- [ ] It is still running after 10 minutes, untended

If CPU is pegged at the vCPU count with one camera, the hotel cannot have many more on this server. That is the moment to discuss Path B, not after they have signed.

---

## 7. Tell the hotel plainly

- Which account you were given, and that it is read-only
- That video is processed and stored **on your server, not in their building**
- How long recordings are kept (default 30 days)
- Whether face recognition is on — **and offer to turn it off**. For a hotel, detecting people and vehicles is usually enough; naming individuals needs a conversation about consent and staff relations

Being clear about this before an incident is worth more than any feature.

---

## 8. When it does not work

| Symptom | Cause | Fix |
|---|---|---|
| `401 Unauthorized` | Wrong credentials, or special characters in the password | Test in VLC; URL-encode `@ : / ?` in the password |
| Connection timed out | NVR not reachable from the VPS | Confirm the tunnel first |
| Picture is black or green | Wrong stream path | Use the exact URL VLC played |
| Live works, no events | Detection running but zones or thresholds excluding it | Walk directly in front of the camera, check the event list |
| `503` on adding a camera | API still in cloud-only mode | `docker logs smartcam \| grep -i cloud-only` — should say "source(s)" |
| Whole site slow | CPU saturated by the main stream | Switch to the sub-stream |

---

## 9. Say this honestly about limits

One VPS handles a handful of camera streams — measure, do not guess. The permanent answer at scale is **Path B**: `edge_agent.py` runs detection at the site, buffers locally, and pushes only events and clips upstream, so bandwidth and CPU stop being a per-camera cost on the server.

The agent needs Python and PyTorch on-site, which means a small PC or a Raspberry Pi class box. That is a customer deployment, not a demo.
