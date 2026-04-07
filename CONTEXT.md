# Anti-UAV Detection System — Context Transfer

Paste this into a new Kiro chat to pick up where we left off.

---

## Project Summary

Full anti-UAV detection system. Two-laptop setup connected via phone WiFi hotspot.

- **Main laptop** (`10.202.14.6`) — Docker stack: MQTT broker, aggregation, signaling, web frontend, HA bridge
- **Edge laptop** (`10.202.14.187`) — Python inference via `launcher_edge.py`
- **Phone** (`10.202.14.184`) — WiFi hotspot + IP Webcam camera source

OS: CachyOS (Arch-based), fish shell on both laptops.

---

## Trained Models (from UAV-dataset-workflow)

Four YOLO26s models trained and evaluated. **Recommended production model: BirdDrone-2C-FT.**

| Model | Classes | mAP@0.5 | mAP@0.5:0.95 | Hardware | Weights path |
|---|---|---|---|---|---|
| BirdDrone-2C | Bird, Drone | 0.926 | 0.554 | RTX 2070 | `training/run_2class_yolo26s_rtx2070_100ep/weights/best.pt` |
| BirdDrone-3C | Bird, Drone, UAV | 0.892 | 0.574 | Colab T4 | `training/run_3class_yolo26s_colab_t4_100ep/weights/best.pt` |
| BirdDrone-2C-FT | Bird, Drone | 0.969* | 0.678* | RTX 2070 | `training/finetuned/BirdDrone-2C/weights/best.pt` |
| BirdDrone-3C-FT | Bird, Drone, UAV | 0.881* | 0.598* | RTX 2070 | `training/finetuned/BirdDrone-3C/weights/best.pt` |

*On combined val set (original + DUT Anti-UAV pseudo-labels)

**Canonical classes:**
- `Bird` — confuser class (not a threat)
- `Drone` — small consumer/commercial drones, quadcopters
- `UAV` — large UAVs, fixed-wing (3-class models only)

**DUT Anti-UAV evaluation (20 videos):**
- BirdDrone-2C-FT: avg detection rate 0.818, avg confidence 0.790, bird false alarm rate 0.3%
- BirdDrone-3C-FT: avg detection rate 0.883, avg confidence 0.824, bird false alarm rate 4.5%

---

## Stack Status — Main Device (RUNNING)

All Docker services running and healthy:

| Service | Port | Notes |
|---|---|---|
| mosquitto | 8883 (TLS+cert, external) / 1883 (plain, internal) | MQTT broker |
| aggregation | 8001 (internal) | FastAPI, connects to MQTT on port 1883 |
| control-center | 8080 | Serves React frontend + JWT auth |
| signaling | 8090 (0.0.0.0) | WebRTC signaling (Node.js) — must be 0.0.0.0 for edge access |
| ha_bridge | — | Silent backend data bridge (internal only) |

Frontend at `http://localhost:8080` — "Anti-UAV Control Center" (v2)
- Login portal with invite-token registration and audit trail
- Sidebar navigation: Overview, Map, Live Feeds, Devices, PTZ, Logs, Settings
- HA-inspired card UI with design tokens
- Map with slide-in device panel (live feed, health, sensor, PTZ)
- Per-class detection color coding (drone=red, bird=amber, person=blue)

Start/stop via `launcher_main.py` (tkinter GUI, simplified).

---

## Stack Status — Edge Device (RUNNING)

Edge device at `10.202.14.187` running inference.

### What works
- MQTT connected to main laptop on port 8883 with TLS + client cert
- Camera: phone IP Webcam at `http://10.202.14.184:8080/video`
- Inference running with `yolov8n.pt` (placeholder — replace with BirdDrone-2C-FT)
- Edge device appears on Overview and Map
- Health reporter publishing CPU/memory/FPS every 30s
- WebRTC streaming works (signaling on 0.0.0.0:8090)

### Edge config (`edge/config.yaml`)
```yaml
device_id: edge-01
mqtt:
  host: 10.202.14.6
  port: 8883
  tls:
    ca_cert: /home/mubarak/Project/UAV-2/UAV/secrets/ca.crt
    client_cert: /home/mubarak/Project/UAV-2/UAV/secrets/edge-01.crt
    client_key: /home/mubarak/Project/UAV-2/UAV/secrets/edge-01.key
camera:
  source: http://10.202.14.184:8080/video
  fps: 15
location:
  lat: 15.628
  lon: 32.489
active_model: daylight-v1
model_profiles:
  - name: daylight-v1
    file_path: /home/mubarak/Project/UAV-2/UAV/yolov8n.pt
    camera_mode: daylight
signaling:
  url: ws://10.202.14.6:8090
```

**To use the real trained model**, update `file_path` to the BirdDrone-2C-FT weights and add class colors:
```yaml
model_profiles:
  - name: BirdDrone-2C-FT
    file_path: /path/to/UAV-dataset-workflow/training/finetuned/BirdDrone-2C/weights/best.pt
    camera_mode: daylight
    class_colors:
      Bird: "#f59e0b"
      Drone: "#ef4444"
```

---

## Known Issues / Fixes Applied

### Certs
- `certs/gen_certs.sh` — includes IP SAN in server cert when `SERVER_IP` is set
- Current server cert valid for `10.202.14.6` (regenerated April 2026)
- Cert files in `secrets/` — NOT in git, generate locally

### Edge device
- `lap>=0.5.12` must be installed in venv: `.venv/bin/pip install lap`
- Set `YOLO_AUTOINSTALL=false` to prevent ultralytics auto-install attempts
- Kill stale `edge.main` processes before starting: `pkill -f edge.main`
- Signaling server must bind to `0.0.0.0:8090` (not `127.0.0.1`) for edge access

### Docker / Main
- Mosquitto runs as root (`user: root` in compose) so it can read secrets volume
- Mosquitto has two listeners: 1883 plain (internal Docker) + 8883 TLS (external)
- Aggregation connects on port 1883 (no TLS needed internally)
- Signaling port changed from `127.0.0.1:8090` to `0.0.0.0:8090`
- Auth DB persisted in Docker volume `control-center-data` at `/app/data/auth.db`

---

## File Structure

```
UAV/
├── edge/                  # Edge device Python inference stack
│   ├── main.py            # Entry point
│   ├── camera.py          # OpenCV + HTTP MJPEG capture
│   ├── inference_engine.py# YOLO + ByteTrack
│   ├── mqtt_client.py     # Publishes to MQTT + cert_info extraction
│   ├── command_handler.py # Handles commands from control center
│   ├── ptz_controller.py  # PTZ control (optional)
│   ├── sensor_reader.py   # Sensor polling (optional)
│   ├── estimator.py       # Distance/trajectory estimation (optional)
│   ├── webrtc_streamer.py # WebRTC live stream
│   ├── payload.py         # Payload dataclasses
│   ├── config.py          # Config loader/validator
│   ├── health_reporter.py # Publishes CPU/memory/FPS to uav/health/
│   └── log_publisher.py   # Publishes WARNING+ logs to uav/log/
├── main/
│   ├── aggregation/       # FastAPI aggregation service
│   ├── control-center/    # FastAPI frontend proxy + JWT auth
│   ├── signaling/         # Node.js WebRTC signaling
│   └── ha_bridge/         # Silent backend data bridge
├── frontend/              # React/TypeScript control center UI (v2)
├── docker/                # Docker Compose + Mosquitto config
├── shared/schemas/        # JSON schemas for MQTT payloads
├── secrets/               # TLS certs (NOT in git, generate locally)
├── certs/gen_certs.sh     # Cert generation script
├── launcher_main.py       # Main device GUI launcher (simplified)
├── launcher_edge.py       # Edge device GUI launcher (simplified)
├── workflow.md            # System workflow documentation
├── CONTEXT.md             # This file
└── INSTRUCTIONS.md        # Setup & run instructions
```

---

## MQTT Topics

| Topic | Direction | Description |
|---|---|---|
| `uav/tracking/{id}` | Edge → Main | Detection results per frame |
| `uav/status/{id}` | Edge → Main | Online/offline + model + cert_info (retained) |
| `uav/health/{id}` | Edge → Main | CPU, memory, FPS, uptime (every 30s) |
| `uav/log/{id}` | Edge → Main | WARNING+ log entries |
| `uav/sensor/{id}` | Edge → Main | Compass bearing, pitch |
| `uav/ptz/status/{id}` | Edge → Main | PTZ position after each command |
| `uav/command/{id}` | Main → Edge | start_stream, stop_stream, switch_model |
| `uav/ptz/{id}` | Main → Edge | pan, tilt, zoom commands |

---

## Resuming Edge Device Work

```fish
# On edge laptop — kill any stale processes first
pkill -f edge.main

# Start launcher
cd /home/mubarak/Project/UAV-2/UAV
python3 launcher_edge.py
```

Cert files are NOT in git — regenerate on main laptop if IPs change:
```fish
FORCE=1 SERVER_IP="10.202.14.6" DEVICE_IDS="edge-01" bash certs/gen_certs.sh
docker compose -f docker/docker-compose.yml restart mosquitto
# Then copy new certs to edge laptop
scp secrets/ca.crt secrets/edge-01.crt secrets/edge-01.key mubarak@10.202.14.187:/home/mubarak/Project/UAV-2/UAV/secrets/
```

---

## Auth System (v2)

- Bootstrap admin: `admin` / `changeme` (set in `docker/.env`)
- Change password: Settings → Users → Generate Invite → create new admin → deactivate old
- Invite tokens: `UAV-XXXX-XXXX` format, up to 30 days expiry
- Roles: `admin` (full access) | `viewer` (read-only, no commands)
- Audit log: every PTZ/command action logged with username + timestamp
- Auth DB: persisted in Docker volume, survives restarts
