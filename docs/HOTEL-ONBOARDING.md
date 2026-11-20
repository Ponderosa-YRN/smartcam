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

---

## 10. Hikvision NVR — specifics

### 10.1 The account

In the NVR web interface: **System → User Management → Add**.

Give it **Remote: Live View** (and Playback if they allow). Leave camera configuration, remote configuration and shutdown unchecked. There is no reason for SmartCam to have admin.

Note the username and password exactly. **Passwords with `@ : / ? #` must be URL-encoded** in the RTSP URL — `@` becomes `%40`, `:` becomes `%3A`, `/` becomes `%2F`. A password containing `@` is the single most common cause of "it works in the NVR but not from outside".

### 10.2 The URL

Hikvision uses `/Streaming/Channels/<channel><stream>`, where channel is the camera number and stream is `01` (main) or `02` (sub):

| Camera | Main | Sub |
|---|---|---|
| 1 | `rtsp://user:pass@IP:554/Streaming/Channels/101` | `.../102` |
| 2 | `.../201` | `.../202` |
| 3 | `.../301` | `.../302` |
| 12 | `.../1201` | `.../1202` |

RTSP port is 554 by default. If it was changed, **Network → Advanced → Network Port** shows the real one.

### 10.3 Test carefully — lockout is real

**Hikvision locks an account after a handful of failed logins** — typically 5 to 7 attempts, for around 30 minutes, and it tells you only "illegal login". If you spend an afternoon guessing a password, you will lock the account and then nothing works until someone resets it.

So:

1. Test **one** URL in VLC, with the password you believe is correct
2. If it fails, **stop and check the password with the hotel** rather than trying variants
3. Confirm the tunnel with `ping` before attempting any RTSP login — a timeout is a network problem, not a password problem, and doesn't count against the lockout

### 10.4 Check the sub-stream is enabled, and its codec

Two settings decide whether this is fast or painful.

**Is the sub-stream on?** Some NVRs ship with it disabled. If `.../102` fails but `.../101` works, that's the cause. Enable it in **Camera → Video/Audio → Sub Stream**, at 704×576 or 1280×720.

**Is it H.264 or H.265?** Newer Hikvision defaults to **H.265**, which costs roughly double the CPU to decode. If the sub-stream is H.265 and the site will run more than two or three cameras, ask to switch it to H.264 — the picture difference at that resolution is negligible and the CPU saving is not.

Note this in your write-up either way; it decides how many cameras that site can run on your server.

### 10.5 Map channels to names before you add them

Channel 1 is whatever camera is plugged into port 1, and it is almost never "the gate".

In the NVR: **Camera Management** shows channel, camera name and IP. Write the mapping down:

| Ch | NVR name | Where it actually points |
|---|---|---|
| 1 | | |
| 2 | | |

Wrong names produce alerts labelled with the wrong place, which loses trust faster than a missing alert. Add two or three cameras first, verify the labels match reality, then add the rest.

### 10.6 Hikvision failure table

| Symptom | Cause |
|---|---|
| `401` / "illegal login" | Wrong password, unencoded special character, or the account is locked |
| Timeout | Tunnel down, wrong IP, or RTSP port not 554 |
| `101` works, `102` fails | Sub-stream disabled on the NVR |
| Black or green frames | Wrong channel number, or camera not on that channel |
| Works, then drops | Hikvision limits concurrent streams per camera (often 6) |
| Very high CPU | H.265, or you are on the main stream |
### 10.7 A verified install — DS-7232GHI-K2 on firmware V4.30

These are the values that worked end to end on a real hotel DVR, measured rather than assumed.
Copy them for the next Hikvision site and change only the addresses.

**On the DVR**

| Setting | Path | Value |
|---|---|---|
| Address | Network → **General → TCP/IP** | DHCP **off**; IPv4 fixed, mask /24, gateway .1 |
| RTSP port | Network → **More Settings** | **554** — that tab is where it lives on V4.30, not "Advanced" |
| HTTP / server | Network → More Settings | 80 / 8000 |
| Output Bandwidth Limit | Network → More Settings | **leave unticked** — it caps the whole DVR's egress |
| Encoding | Camera → Video/Audio → Main Stream | **H.264**, 960×1080, 15 fps, 4096 Kbps |
| Sub-stream | Camera → Video/Audio → Sub Stream | left at CIF — **do not use it**, see below |
| Account | System → User Management | read-only operator, Remote: Live View only |

**On the server**

| Step | Value |
|---|---|
| Stream URL | `rtsp://USER:PASS@DVR-IP:554/Streaming/Channels/101` |
| Transport | TCP — the default since `46e3e34`; no environment variable needed |
| Save | Settings page → **Save changes** at the bottom, then `docker restart smartcam` |

**Measured on a 4 vCPU / 16 GB VPS**

| Metric | Value |
|---|---|
| Resolution received | 960×1080 |
| CPU, one camera, light scene | **9.5%** |
| Memory | ~620 MB |

At that cost the box holds roughly 8–10 cameras on a quiet scene, fewer when the scene is busy.
Measure again with real footfall before quoting a number to a hotel.

**The four things that cost time, in order**

1. **DHCP moved the DVR** from `.53` to `.7` between visits, so the configured URL pointed at a
   different device that refused port 554. Disable DHCP on every device you touch.
2. **The sub-stream was CIF 352×288.** A person is about 25 px tall at 15 m — YOLO cannot detect
   that. Use the main stream.
3. **H.265 defaults on.** It doubles decode cost and over a tunnel produces `hevc` PPS/POC errors
   and dropped frames. Set H.264 on every channel used.
4. **The Settings page has one page-level Save.** Adding a camera row does nothing until
   **Save changes** is pressed and reads `Saved`.

**Watching for silent failure**

A crashing camera shows no error. `docker stats` near 0% with a camera configured means no stream
is being decoded; check `docker logs` for `crashed` (added in `60dbd57`).

