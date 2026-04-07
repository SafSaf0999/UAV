# Anti-UAV Detection System — Workflow Guide

## What This System Does

This system detects and tracks unmanned aerial vehicles (UAVs/drones) in real time using AI inference on distributed edge devices. A central control center aggregates all detections, streams live video, and lets operators monitor and control everything from a web browser or phone.

---

## Hardware Overview

```
Phone (WiFi Hotspot + IP Webcam)
        │
        ├── Main Laptop  ←── runs Docker stack (broker, aggregation, control center)
        │
        └── Edge Laptop  ←── runs YOLO inference, publishes detections
```

- **Phone** — acts as WiFi router connecting both laptops, and runs IP Webcam as the camera source
- **Main Laptop** — hosts all server-side services in Docker
- **Edge Laptop** — runs the AI inference pipeline and streams video

---

## System Architecture

```
Edge Device                          Main Device (Docker)
──────────────────────────────       ──────────────────────────────────────────
Camera (IP Webcam / USB / RTSP)      Mosquitto MQTT Broker (port 8883, TLS)
        │                                    │
        ▼                                    ▼
YOLO Inference Engine            Aggregation Service (FastAPI)
        │                                    │
        ├── Tracking Payloads ──MQTT──►      ├── Validates & stores device state
        ├── Status (online/offline)          ├── Pushes updates via WebSocket
        ├── Health (CPU, FPS, uptime)        └── REST API for commands
        └── Logs (WARNING+)
                                     Control Center (FastAPI + React)
WebRTC Streamer ──────────────────►          │
        │                                    ├── Serves the web UI
        └── Live video stream                ├── JWT authentication
                                             ├── Proxies API to aggregation
Signaling Server (Node.js) ◄────────────────┘
        │
        └── Brokers WebRTC connection between edge and browser

                                     Backend Data Bridge
                                             │
                                             └── Forwards UAV state to external
                                                 automation systems silently
```

---

## Data Flow — Detection

1. Camera captures a frame
2. YOLO model runs inference → detects drones, birds, etc.
3. ByteTrack assigns persistent track IDs across frames
4. Edge device publishes a **Tracking Payload** to MQTT topic `uav/tracking/edge-01`
5. Aggregation service receives it, validates the JSON schema, updates device state
6. Aggregation pushes the update via WebSocket to all connected browsers
7. Control center frontend draws bounding boxes on the live feed overlay
8. Map marker turns red and shows a detection alert

---

## Data Flow — Live Video

1. Operator clicks **Stream** on a device card (or it auto-starts when the Live Feeds page opens)
2. Control center sends `start_stream` command via MQTT to the edge device
3. Edge device starts a WebRTC peer connection and registers with the signaling server
4. Browser connects to the signaling server as a subscriber
5. SDP offer/answer and ICE candidates are exchanged through the signaling server
6. Video flows directly from the edge device to the browser (peer-to-peer, DTLS-SRTP encrypted)

---

## Control Center — Pages

### Overview
The home page. Shows 4 summary cards (total devices, online now, active detections, alerting devices) and a grid of device cards. Each card shows:
- Online/offline status
- Uptime
- Active model name
- Per-class detection counts (e.g. `drone ×2  bird ×1`)
- Last detection timestamp
- Quick buttons: View detail, Start stream

### Map
Interactive map (OpenStreetMap) with a marker per edge device at its configured GPS coordinates.
- Green marker = online, grey = offline, red = active detection
- Click any marker → slide-in panel with live feed, health stats, sensor data, PTZ controls, and quick actions

### Live Feeds
Up to 4 simultaneous WebRTC video streams in a grid. Streams auto-start when the page opens. Each feed shows:
- Bounding boxes color-coded by class (drone = red, bird = amber, etc.)
- Track ID and confidence score
- Class legend in the corner
- "Waiting for stream…" or "Stream interrupted" states

### Devices
Same as Overview — full list of all known devices.

### Device Detail
Full-page view for one device. Shows:
- Health gauges (CPU %, memory %, inference FPS)
- Certificate info (CN, expiry date, issuer)
- Active model and all configured model profiles
- Last 50 detections with timestamp, label, confidence

### PTZ
Pan/Tilt/Zoom controls for devices with PTZ capability. Joystick for continuous pan/tilt, buttons for zoom and home, absolute angle inputs.

### Logs
Structured log viewer for WARNING+ messages from all edge devices. Filter by device, level, and time range. Export to CSV.

### Settings
- Theme toggle (dark/light)
- User management (admin only): invite token generation, user list, deactivate users
- Audit log (admin only): every command issued by every user with timestamp

---

## Authentication Flow

```
Admin generates invite token (UAV-XXXX-XXXX, up to 30 days)
        │
        └── Shares token out-of-band (message, email, etc.)
                │
                ▼
New user visits /register?token=UAV-XXXX-XXXX
        │
        └── Fills in display name, username, password
                │
                ▼
Account created, token consumed (single-use)
        │
        └── JWT issued → stored in browser localStorage
                │
                ▼
Every API request carries Authorization: Bearer <JWT>
Every PTZ/command action is written to the audit log
```

**Roles:**
- `admin` — full access: PTZ, commands, model switching, user management, audit log
- `viewer` — read-only: can see all data but cannot issue commands

---

## Edge Device Startup Sequence

```
1. launcher_edge.py opens
2. Auto-detects TLS certs in ./secrets/
3. Loads edge/config.yaml
4. Starts CameraSource thread (connects to IP Webcam, retries every 5s on failure)
5. Loads YOLO model from configured .pt file path
6. Starts InferenceEngine thread (reads frames, runs YOLO + ByteTrack)
7. Connects to MQTT broker with TLS client certificate
8. Publishes retained online status to uav/status/edge-01
9. Starts HealthReporter (publishes CPU/memory/FPS every 30s)
10. Attaches MQTT log handler (WARNING+ logs published to uav/log/edge-01)
11. Waits for start_stream command to begin WebRTC streaming
```

---

## Main Device Startup Sequence

```
1. launcher_main.py opens (or: docker compose up -d --build)
2. Mosquitto starts — TLS broker on port 8883
3. Aggregation service starts — subscribes to all uav/# topics
4. Frontend builder runs — compiles React app into dist/
5. Control center starts — serves frontend, JWT auth, proxies to aggregation
6. Signaling server starts — WebRTC SDP/ICE relay on port 8090
7. Backend data bridge starts — forwards UAV state to external automation systems
8. Open browser at http://localhost:8080
9. Log in with admin credentials
```

---

## MQTT Topics Reference

| Topic | Direction | Description |
|---|---|---|
| `uav/tracking/{id}` | Edge → Main | Detection results per frame |
| `uav/status/{id}` | Edge → Main | Online/offline + model name (retained) |
| `uav/health/{id}` | Edge → Main | CPU, memory, FPS, uptime |
| `uav/log/{id}` | Edge → Main | WARNING+ log entries |
| `uav/sensor/{id}` | Edge → Main | Compass bearing, pitch |
| `uav/ptz/status/{id}` | Edge → Main | PTZ position after each command |
| `uav/command/{id}` | Main → Edge | start_stream, stop_stream, switch_model |
| `uav/ptz/{id}` | Main → Edge | pan, tilt, zoom commands |

---

## Model Switching

Operators can switch the active YOLO model on any edge device at runtime without restarting:

1. Go to Overview → device card → Switch Model (or Device Detail → Model section)
2. Enter the model profile name (e.g. `thermal-v1`)
3. Control center publishes `switch_model` command via MQTT
4. Edge device pauses inference, loads new `.pt` file in background (≤5s timeout)
5. Atomically swaps the model, resumes inference
6. Status message updates with new active model name

Model profiles are defined in `edge/config.yaml`:
```yaml
model_profiles:
  - name: BirdDrone-2C-FT          # Recommended — Bird/Drone, mAP@0.5=0.969
    file_path: /path/to/training/finetuned/BirdDrone-2C/weights/best.pt
    camera_mode: daylight
    class_colors:
      Bird: "#f59e0b"
      Drone: "#ef4444"
  - name: BirdDrone-3C-FT          # 3-class — Bird/Drone/UAV, mAP@0.5=0.881
    file_path: /path/to/training/finetuned/BirdDrone-3C/weights/best.pt
    camera_mode: daylight
    class_colors:
      Bird: "#f59e0b"
      Drone: "#ef4444"
      UAV: "#8b5cf6"
  - name: thermal-v1               # Future — thermal preprocessing
    file_path: /path/to/thermal.pt
    camera_mode: thermal            # applies CLAHE + colormap preprocessing
```

---

## Remote Access (Android)

1. Install WireGuard on Android
2. Import the peer config QR code (see `docker/wireguard/android-peer.md`)
3. Connect to VPN → open `http://10.0.0.1:8080` in Chrome
4. Log in → tap ⋮ → **Add to Home Screen** → installs as standalone app

---

## Trained Models

The system uses YOLO26s models trained on curated aerial imagery datasets. Four models are available:

| Model | Classes | mAP@0.5 | mAP@0.5:0.95 | Notes |
|---|---|---|---|---|
| BirdDrone-2C | Bird, Drone | 0.926 | 0.554 | Base 2-class model |
| BirdDrone-3C | Bird, Drone, UAV | 0.892 | 0.574 | Base 3-class model |
| BirdDrone-2C-FT | Bird, Drone | 0.969* | 0.678* | **Recommended** — fine-tuned on DUT Anti-UAV |
| BirdDrone-3C-FT | Bird, Drone, UAV | 0.881* | 0.598* | Fine-tuned 3-class |

*On combined val set (original + DUT Anti-UAV pseudo-labels)

**Recommended production model:** BirdDrone-2C-FT — best bird discrimination (0.3% false alarm rate), lowest false positive rate, minimal regression on original test sets.

Training details: `UAV-dataset-workflow/documentations/`
Weights: `UAV-dataset-workflow/training/`

---

## TLS Security

All MQTT traffic is encrypted with TLS. Each edge device has its own client certificate:

```
secrets/
  ca.crt          ← Certificate Authority (trusted by all)
  server.crt/key  ← Mosquitto broker certificate (includes IP SAN)
  edge-01.crt/key ← Edge device client certificate
```

To regenerate certs (e.g. after IP change):
```bash
FORCE=1 SERVER_IP="10.202.14.6" DEVICE_IDS="edge-01" bash certs/gen_certs.sh
docker compose restart mosquitto
# Then copy new certs to edge device
```

---

## Quick Troubleshooting

| Symptom | Check |
|---|---|
| Edge device not appearing on dashboard | `docker compose logs aggregation` — check MQTT subscription |
| MQTT TLS error on edge | Regenerate certs with correct `SERVER_IP`, restart mosquitto |
| Live feed shows black / waiting | Start IP Webcam on phone first, then click Stream |
| Bounding boxes misaligned | Video dimensions mismatch — fixed automatically via `loadedmetadata` event |
| Login fails | Check `BOOTSTRAP_ADMIN_PASSWORD` in `docker/.env` |
| Camera test fails (no module cv2) | Run from `.venv/bin/python3`, not system python |
