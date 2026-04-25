# Anti-UAV Detection System — Project Reference

This is the single reference document for the Anti-UAV Detection System. It covers the project summary, hardware setup, system architecture, all services, data flows, configuration, and operational procedures.

---

## 1. Project Summary

A distributed real-time anti-UAV detection system built on edge computing and a centralised web-based control center. Edge devices run YOLO26s inference on local camera feeds and publish detections over MQTT. The control center aggregates all data, streams live video via WebRTC, and lets operators monitor and control everything from a browser or the desktop app.

**Hardware:**
- **Main device** — runs the Docker stack (MQTT broker, aggregation, control center, signaling, tile server)
- **Edge device** — runs Python inference via `launcher_edge.py` or headless
- **Camera source** — IP Webcam app (Android), USB webcam, or any RTSP/MJPEG stream on the same network

**OS:** CachyOS (Arch-based), fish shell on both devices.

**Current network (update when IPs change):**

| Device | IP |
|---|---|
| Main device | `10.196.175.6` |
| Edge device | `10.196.175.187` |

---

## 2. Repository Structure

```
UAV/                          ← Git repo root (testing branch)
├── edge/                     ← Edge device Python inference stack
│   ├── main.py               ← Entry point
│   ├── camera.py             ← MJPEG/RTSP/USB capture with auto-retry
│   ├── inference_engine.py   ← YOLO26s + ByteTrack
│   ├── mqtt_client.py        ← MQTT with username/password auth (primary)
│   ├── command_handler.py    ← Handles: start/stop_stream, switch_model, update_config, ipwebcam_*
│   ├── ipwebcam_handler.py   ← IP Webcam HTTP API proxy (zoom, torch, ISO, exposure, snapshot)
│   ├── webrtc_streamer.py    ← WebRTC peer connection + signaling
│   ├── health_reporter.py    ← Publishes CPU/memory/FPS every 30s
│   ├── log_publisher.py      ← Publishes WARNING+ logs to MQTT
│   ├── ptz_controller.py     ← PTZ camera control (digital + hardware)
│   ├── sensor_reader.py      ← Compass/pitch sensor polling
│   ├── estimator.py          ← Distance + trajectory estimation
│   ├── payload.py            ← Detection payload serialisation
│   ├── config.py             ← Config loader/validator
│   ├── config.example.yaml   ← Example config with all fields documented
│   └── edge_sim.py           ← Simulated edge device for PTZ follow testing
│
├── main/
│   ├── aggregation/          ← FastAPI: MQTT subscriber, device registry, WebSocket push
│   │   ├── app.py            ← REST endpoints + WebSocket + lifespan
│   │   ├── registry.py       ← DeviceState + DeviceRegistry
│   │   ├── mqtt_subscriber.py← Subscribes to all uav/# topics
│   │   ├── detections_db.py  ← SQLite persistence for detection history
│   │   ├── thresholds.py     ← Per-device alert threshold config
│   │   ├── webhook_dispatcher.py ← HMAC-signed webhook delivery
│   │   ├── health_checker.py ← Background health timeout checker
│   │   └── ptz_follow.py     ← Bearing computation for multi-device PTZ follow
│   ├── control-center/       ← FastAPI: JWT auth, API proxy, frontend serving
│   │   ├── app.py            ← Routes + middleware
│   │   └── auth.py           ← JWT, sessions, tokens, webhooks, users
│   ├── signaling/            ← Node.js WebRTC SDP/ICE relay
│   └── ha_bridge/            ← Silent backend data bridge
│
├── frontend/                 ← React/TypeScript control center UI
│   └── src/
│       ├── pages/            ← OverviewPage, MapView, LiveFeedGrid, DeviceDetailPage, LogsPage, SettingsPage
│       ├── components/       ← DeviceCard, TrackingOverlay, MapPanel, PtzControls, HealthGauges, etc.
│       ├── api/              ← auth.ts, commands.ts, websocket.ts
│       └── utils/            ← classColors.ts, auth.ts, formatUptime.ts
│
├── electron/                 ← Electron desktop app
│   ├── main.js               ← Starts Docker stack, polls localhost:8080, tray icon
│   ├── preload.js            ← Minimal context bridge
│   ├── package.json
│   ├── electron-builder.yml  ← AppImage build config
│   └── PKGBUILD              ← Arch Linux package
│
├── docker/
│   ├── docker-compose.yml    ← All services (tile-server via --profile tiles)
│   ├── .env.example          ← Template for docker/.env
│   └── mosquitto/            ← Mosquitto config + entrypoint
│
├── certs/
│   └── gen_certs.sh          ← Generates CA + server cert only (no client certs)
│
├── secrets/                  ← TLS certs (NOT in git — generate locally)
│   ├── ca.crt / ca.key
│   └── server.crt / server.key
│
├── shared/schemas/           ← JSON schemas for MQTT payloads
├── launcher_main.py          ← Main device GUI launcher (tabbed, dark theme)
├── launcher_edge.py          ← Edge device GUI launcher (tabbed, dark theme)
├── report_full.pdf           ← Full project report (56 pages)
├── README.md                 ← GitHub README
├── PROJECT.md                ← This file
├── EDGE_SETUP.md             ← Edge device setup guide
└── UAV-dataset-workflow/     ← Dataset management + YOLO training toolkit
    ├── anti_uav/             ← Python package (GUI, CLI, training pipeline)
    ├── training/             ← Model weights (tracked via Git LFS)
    │   └── finetuned/BirdDrone-2C/weights/best.pt  ← Production model
    ├── documentations/       ← report_full.tex + figures
    └── launch.py             ← Dataset workflow launcher
```

---

## 3. Docker Services

All services run on the internal `uav-net` Docker network. Start with:

```fish
# Standard (internet map tiles)
sudo docker compose -f docker/docker-compose.yml up -d

# With offline tile server
sudo docker compose -f docker/docker-compose.yml --profile tiles up -d
```

| Service | Port | Role |
|---|---|---|
| mosquitto | 8883 (TLS+password, external) / 1883 (plain, internal) | MQTT broker |
| aggregation | 8001 (internal) | FastAPI — device state, WebSocket push, detection DB |
| frontend-builder | — | One-shot React compiler → `frontend-dist` volume |
| control-center | 8080 | FastAPI — serves UI, JWT auth, proxies to aggregation |
| signaling | 8090 (0.0.0.0) | Node.js WebRTC SDP/ICE relay — must bind 0.0.0.0 for edge access |
| ha_bridge | — | Silent backend data bridge |
| tile-server | 8070 (optional) | Self-hosted OSM tiles for offline map |

**Key design notes:**
- Aggregation connects to Mosquitto on port **1883** (plain, no TLS) — both are on the same trusted Docker network
- The `frontend-dist` volume is shared between `frontend-builder` (writes) and `control-center` (reads)
- The signaling server must bind to `0.0.0.0:8090` so edge devices on the LAN can reach it

---

## 4. MQTT Topics

| Topic | Direction | QoS | Description |
|---|---|---|---|
| `uav/tracking/{id}` | Edge → Main | 0 | Detections per frame (bbox, label, confidence, track_id) |
| `uav/status/{id}` | Edge → Main | 1 | Online/offline + model + GPS (retained) |
| `uav/health/{id}` | Edge → Main | 0 | CPU, memory, FPS, uptime (every 30s) |
| `uav/log/{id}` | Edge → Main | 0 | WARNING+ log entries |
| `uav/sensor/{id}` | Edge → Main | 0 | Compass bearing, pitch |
| `uav/ptz/status/{id}` | Edge → Main | 0 | PTZ position after command |
| `uav/ipwebcam/capabilities/{id}` | Edge → Main | 0 | IP Webcam available settings (on startup) |
| `uav/ipwebcam/sensors/{id}` | Edge → Main | 0 | Battery, light, motion, pressure (every 30s) |
| `uav/snapshot/{id}` | Edge → Main | 0 | Base64 JPEG snapshot (on demand) |
| `uav/command/{id}` | Main → Edge | 1 | start_stream, stop_stream, switch_model, update_config, ipwebcam_control, ipwebcam_sensors |
| `uav/ptz/{id}` | Main → Edge | 0 | pan, tilt, zoom, pan_to_bearing |

---

## 5. Trained Models

| Model | Classes | mAP@0.5 | mAP@0.5:0.95 | Weights |
|---|---|---|---|---|
| BirdDrone-2C | Bird, Drone | 0.926 | 0.554 | `training/run_2class_.../weights/best.pt` |
| BirdDrone-3C | Bird, Drone, UAV | 0.892 | 0.574 | `training/run_3class_.../weights/best.pt` |
| **BirdDrone-2C-FT** | **Bird, Drone** | **0.969*** | **0.678*** | **`training/finetuned/BirdDrone-2C/weights/best.pt`** |
| BirdDrone-3C-FT | Bird, Drone, UAV | 0.881* | 0.598* | `training/finetuned/BirdDrone-3C/weights/best.pt` |

*On combined val set. **Recommended production model: BirdDrone-2C-FT** — 0.3% bird false alarm rate.

**Bounding box colors:** Bird = green (#22c55e), Drone ≥50% confidence = red (#ef4444), Drone <50% = orange (#f97316)

---

## 6. Authentication

**Web (JWT):**
- Admin generates invite token (`UAV-XXXX-XXXX`, up to 30 days) in Settings → Tokens
- New user visits `/register?token=UAV-XXXX-XXXX`, creates account
- Roles: `admin` (full access) | `viewer` (read-only)
- Every PTZ/command action logged to audit trail with username + timestamp
- Sessions visible and revocable in Settings → Sessions

**MQTT:**
- Edge devices authenticate with `mqtt.username` + `mqtt.password` from `edge/config.yaml`
- Only `ca.crt` needs to be copied to edge device (no client certs)
- Password file: `secrets/passwd` (Mosquitto format)

**Default admin:** `admin` / `changeme` — change immediately after first login.

---

## 7. Starting the System

### Option A — Electron desktop app (recommended)

Launch **Anti-UAV Control Center** from the KDE application launcher.
- Shows loading screen while Docker stack starts
- Opens control center at `http://localhost:8080` when ready
- Close window → dialog: **Minimize to Tray** (keeps stack running) or **Shut Down** (stops all containers)

### Option B — GUI launcher

```fish
python launcher_main.py
```

### Option C — Terminal

```fish
cp docker/.env.example docker/.env
# Edit docker/.env — set JWT_SECRET, admin password, MQTT_AUTH_MODE=password
sudo docker compose -f docker/docker-compose.yml up -d --build
```

### Edge device

```fish
pkill -f edge.main   # kill stale processes
python launcher_edge.py
```

Or headless:
```fish
set -x EDGE_CONFIG (pwd)/edge/config.yaml
set -x YOLO_AUTOINSTALL false
.venv/bin/python -m edge.main
```

---

## 8. Edge Device Config (`edge/config.yaml`)

```yaml
device_id: edge-01

mqtt:
  host: 10.196.175.6        # main device IP
  port: 8883
  username: edge-01         # device_id used as username
  password: "your-password"
  tls:
    ca_cert: ./secrets/ca.crt   # only CA cert needed (no client certs)

camera:
  source: http://<camera-ip>:8080/video   # IP Webcam, or /dev/video0, or rtsp://...
  fps: 15

location:
  lat: 15.628
  lon: 32.489

active_model: BirdDrone-2C-FT

model_profiles:
  - name: BirdDrone-2C-FT
    file_path: /path/to/training/finetuned/BirdDrone-2C/weights/best.pt
    camera_mode: daylight
    class_colors:
      Bird: "#22c55e"
      Drone: "#ef4444"

signaling:
  url: ws://10.196.175.6:8090

# Optional — enables IP Webcam remote controls in Device Detail page
ipwebcam:
  url: http://<phone-ip>:8080

# Optional — makes this device follow another device's detections for PTZ
ptz:
  enabled: false
  hardware_type: digital
  # follow_leader: edge-01   # uncomment to enable PTZ follow
```

---

## 9. TLS Certificates

Only the server cert is needed (no per-device client certs since v3).

```fish
# Generate CA + server cert (run on main device)
FORCE=1 SERVER_IP="10.196.175.6" bash certs/gen_certs.sh

# Restart Mosquitto to pick up new certs
sudo docker compose -f docker/docker-compose.yml restart mosquitto

# Copy only CA cert to edge device
scp secrets/ca.crt mubarak@10.196.175.187:~/Project/UAV-2/UAV/secrets/
```

---

## 10. Offline Map Setup (one-time)

```fish
# Download Sudan region (~136MB, already done)
# /tmp/sudan-latest.osm.pbf

# Import into tile server (10-30 minutes)
sudo docker compose -f docker/docker-compose.yml --profile tiles run --rm \
  -v /tmp/sudan-latest.osm.pbf:/data/region.osm.pbf tile-server import

# Add to docker/.env
echo "TILE_SERVER_URL=http://localhost:8070/{z}/{x}/{y}.png" >> docker/.env

# Start with tile server
sudo docker compose -f docker/docker-compose.yml --profile tiles up -d
```

---

## 11. Control Center Pages

| Page | Description |
|---|---|
| Overview | Summary cards (total/online/detecting/alerting) + device card grid |
| Map | OpenStreetMap with device markers; click → slide-in panel with live feed, health, PTZ |
| Live Feeds | Up to 4 simultaneous WebRTC streams with bounding box overlay |
| Device Detail | Health gauges, model info, detection history, edit config, IP Webcam controls |
| Logs | WARNING+ log viewer, filterable by device/level, CSV export, detection history export |
| Settings | Users, Tokens, Sessions, Notifications (webhooks), Thresholds, Audit log |

---

## 12. IP Webcam Remote Controls

When `ipwebcam.url` is set in edge config, the Device Detail page shows a controls panel:

- **Stream:** zoom (0–100), video resolution, JPEG quality
- **Camera:** torch, front/back camera, night vision, overlay
- **Focus:** focus mode (auto/macro/infinity/fixed), manual focus trigger
- **Exposure:** manual sensor mode, ISO, exposure time (ms), frame duration (ms), aperture, exposure lock, white balance lock
- **Recording:** video recording toggle, snapshot (displays in modal with download)

Phone sensors (battery, light, motion, pressure) are polled every 30s and shown in the health section.

---

## 13. Multi-Device PTZ Follow

Add to `edge/config.yaml` on the follower device:
```yaml
ptz:
  enabled: true
  hardware_type: digital
  follow_leader: edge-01   # device_id of the leader
```

Test without hardware:
```fish
python edge/edge_sim.py --host 10.196.175.6 --username edge-sim --password secret --device-id edge-sim
```

---

## 14. Notification Webhooks

Configure in Settings → Notifications. Events: `detection_alert`, `device_online`, `device_offline`.
Payloads are HMAC-SHA256 signed with a configurable secret (`X-UAV-Signature` header).

---

## 15. Detection History Export

In Logs page → Export Detections: select device, date range → downloads CSV with all detections.

---

## 16. Troubleshooting

| Symptom | Fix |
|---|---|
| Edge not appearing on dashboard | `sudo docker compose logs aggregation` |
| MQTT auth failed | Check username/password in edge config matches `MQTT_PASSWORD_FILE` |
| MQTT TLS error | Regenerate certs with correct `SERVER_IP`, copy `ca.crt` to edge |
| Live feed black / waiting | Start camera source first, then click Stream |
| Camera test fails (no cv2) | Run from `.venv/bin/python3`, not system python |
| Login fails | Check `BOOTSTRAP_ADMIN_PASSWORD` in `docker/.env` |
| Map not loading offline | Run tile server import first (Section 10) |
| Electron hangs on startup | Docker daemon not running: `sudo systemctl start docker` |
| Edge device health timeout (amber) | Edge process crashed or network lost — restart edge |

---

## 17. Dataset Workflow

The `UAV-dataset-workflow/` subfolder contains the full ML pipeline:

```fish
# Launch GUI
python UAV-dataset-workflow/launch.py

# Or CLI
anti-uav                          # full launcher
anti-uav inspect <dataset_path>
anti-uav review <dataset_path>
anti-uav train --profile rtx2070
```

See `UAV-dataset-workflow/README.md` for full documentation.

---

## 18. Android PWA

1. Connect Android to same network as main device
2. Open Chrome → `http://<main-device-ip>:8080`
3. Log in → tap ⋮ → **Add to Home Screen**
4. App installs with the UAV radar icon and opens fullscreen

---

## 19. Data Flow — Detection

1. Camera captures a frame at the configured FPS
2. YOLO26s inference engine runs detection → produces bounding boxes with class labels and confidence scores
3. ByteTrack assigns persistent track IDs across frames so the same drone keeps the same ID
4. Edge device serialises the detection payload as JSON and publishes to `uav/tracking/{device_id}` (QoS 0)
5. Aggregation service receives the message, validates the JSON schema, updates the device state registry
6. Aggregation pushes the update via WebSocket to all connected browser clients
7. Control center frontend draws bounding boxes on the live feed overlay with colour coding
8. Map marker turns red and shows a detection alert badge

---

## 20. Data Flow — Live Video (WebRTC)

1. Operator clicks **Stream** on a device card, or the Live Feeds page auto-starts streams on open
2. Control center sends `start_stream` command via MQTT to the edge device
3. Edge device starts a WebRTC peer connection and registers with the signaling server as a publisher
4. Browser connects to the signaling server as a subscriber for that device
5. SDP offer/answer and ICE candidates are exchanged through the signaling server
6. Video flows directly from the edge device to the browser (peer-to-peer, DTLS-SRTP encrypted)
7. The signaling server is only used for connection setup — it does not relay video

**Black screen fix (applied):** The edge device waits for the first real camera frame before sending the WebRTC offer. The browser calls `video.play()` explicitly on the `canplay` event rather than relying on `autoPlay`.

---

## 21. Data Flow — IP Webcam Controls

1. Operator adjusts a control in the IP Webcam Controls panel (e.g. zoom slider)
2. Frontend sends `POST /api/command/{device_id}` with `{action: "ipwebcam_control", setting: "zoom", value: 50}`
3. Control center proxies to aggregation, which publishes to `uav/command/{device_id}` via MQTT
4. Edge device receives the command, `IPWebcamHandler` calls `GET http://<phone-ip>:8080/zoom?level=50`
5. IP Webcam app on the phone applies the setting immediately
6. For snapshots: edge fetches `photo.jpg`, base64-encodes it, publishes to `uav/snapshot/{device_id}`
7. Aggregation forwards the snapshot via WebSocket to the browser, which displays it in a modal

---

## 22. Edge Device Startup Sequence

```
1.  launcher_edge.py opens (or: python -m edge.main)
2.  Config loaded from edge/config.yaml
3.  CameraSource thread starts — connects to camera, retries every 5s on failure
4.  InferenceEngine thread starts — reads frames, runs YOLO26s + ByteTrack
5.  MQTTClient connects to broker with username/password + TLS (ca.crt only)
6.  LWT registered: if edge crashes, broker publishes offline status automatically
7.  Online status published (retained) to uav/status/{device_id}
8.  HealthReporter starts — publishes CPU/memory/FPS every 30s
9.  MQTTLogHandler attached — WARNING+ logs published to uav/log/{device_id}
10. If ipwebcam.url configured: capabilities fetched and published to uav/ipwebcam/capabilities/{device_id}
11. Waits for start_stream command to begin WebRTC streaming
```

---

## 23. Main Device Startup Sequence

```
1.  Electron app launches (or: docker compose up -d)
2.  Mosquitto starts — TLS broker on port 8883, plain on 1883
3.  Aggregation service starts — subscribes to all uav/# topics, initialises detections.db
4.  Frontend builder runs — compiles React app into frontend-dist volume (one-shot)
5.  Control center starts — serves frontend, JWT auth, proxies to aggregation
6.  Signaling server starts — WebRTC SDP/ICE relay on port 8090
7.  ha_bridge starts — silent backend data bridge
8.  Health checker background task starts — checks device heartbeats every 10s
9.  IP Webcam sensor poller starts — polls sensors every 30s for online devices
10. Open browser at http://localhost:8080
11. Log in with admin credentials
```

---

## 24. Settings Page Reference (Admin Only)

### Users tab
- View all users with role, creation date, last login
- Deactivate users
- Generate invite tokens (UAV-XXXX-XXXX format, up to 30 days)
- Copy token or registration link to clipboard

### Tokens tab
- View all invite tokens with status (pending / used / expired)
- See who used each token and when
- Revoke unused tokens

### Sessions tab
- View all active JWT sessions with username, login time, last seen, user agent
- Revoke individual sessions (invalidates the JWT immediately)

### Notifications tab
- Add webhook URLs for events: `detection_alert`, `device_online`, `device_offline`
- Configure HMAC-SHA256 secret for payload signing
- Enable/disable individual webhooks
- Test webhook (sends test payload, shows HTTP response code)

### Thresholds tab
- Per-device alert configuration:
  - `min_confidence` — minimum detection confidence to trigger alert (default 0.5)
  - `consecutive_frames` — number of consecutive frames with detection before alerting (default 1)
  - `alert_classes` — which classes trigger alerts (default: drone)

### Audit Log tab
- Every PTZ command, model switch, and config push logged with username + timestamp + device

---

## 25. Model Switching at Runtime

Operators can switch the active YOLO model on any edge device without restarting:

1. Go to Device Detail → Edit Config → set Active Model to the profile name
2. Control center publishes `update_config` command via MQTT
3. Edge device pauses inference, loads new `.pt` file (≤5s)
4. Atomically swaps the model, resumes inference
5. Status message updates with new active model name

Model profiles are defined in `edge/config.yaml`:
```yaml
model_profiles:
  - name: BirdDrone-2C-FT
    file_path: /path/to/best.pt
    camera_mode: daylight
    class_colors:
      Bird: "#22c55e"
      Drone: "#ef4444"
  - name: thermal-v1
    file_path: /path/to/thermal.pt
    camera_mode: thermal    # applies CLAHE + colormap preprocessing
```

---

## 26. Health Timeout Detection

The aggregation service runs a background task every 10 seconds checking device heartbeats:

- If a device was `online` and has not sent a health message in **>60 seconds** → status changes to `health_timeout` (amber badge on dashboard)
- If a health message arrives for a `health_timeout` device → status restores to `online`
- If a device disconnects cleanly (LWT) → status is `offline` (grey badge)
- `health_timeout` is distinct from `offline` — it means the process may have crashed without a clean disconnect

---

## 27. Firewall Ports (Main Device)

```fish
sudo ufw allow 8883/tcp   # MQTT broker (edge devices)
sudo ufw allow 8080/tcp   # Control center web UI
sudo ufw allow 8090/tcp   # WebRTC signaling (edge devices)
sudo ufw reload
```

Port 8070 (tile server) is bound to `127.0.0.1` only — no firewall rule needed.

---

## 28. Stopping Everything

### Electron app
Close window → **Shut Down** — stops all containers automatically.

### Terminal
```fish
sudo docker compose -f docker/docker-compose.yml down

# With tile server:
sudo docker compose -f docker/docker-compose.yml --profile tiles down
```

### Edge device
```fish
pkill -f edge.main
# or Ctrl+C in the terminal running python -m edge.main
```
