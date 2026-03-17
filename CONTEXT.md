# Anti-UAV Detection System — Context Transfer

Paste this into a new Kiro chat to pick up where we left off.

---

## Project Summary

Full anti-UAV detection system. Two-laptop setup connected via phone WiFi hotspot.

- **Main laptop** (`10.86.85.6`) — Docker stack: MQTT broker, aggregation, signaling, web frontend
- **Edge laptop** (`10.86.85.187`) — Python inference via `launcher_edge.py`
- **Phone** (`10.86.85.152`) — WiFi hotspot + IP Webcam camera source

OS: CachyOS (Arch-based), fish shell on both laptops.

---

## Stack Status — Main Device (DONE)

All Docker services running and healthy:

| Service | Port | Notes |
|---|---|---|
| mosquitto | 8883 (TLS+cert, external) / 1883 (plain, internal) | MQTT broker |
| aggregation | 8001 (internal) | FastAPI, connects to MQTT on port 1883 |
| control-center | 8080 | Serves React frontend + proxies API |
| signaling | 8090 | WebRTC signaling (Node.js) |

Frontend at `http://localhost:8080` — "Anti-UAV Control Center"
- Dashboard, Map (Leaflet OSM, full viewport), Live Feeds, PTZ tabs
- Map shows world view when no devices; unlocated devices shown in bottom-left panel
- "No devices connected" overlay auto-hides after 3s

Start/stop via `launcher_main.py` (tkinter GUI).

---

## Stack Status — Edge Device (IN PROGRESS)

Edge device was set up and connected successfully. Left off with inference running.

### What works
- MQTT connected to main laptop on port 8883 with TLS + client cert
- Camera: phone IP Webcam at `http://10.86.85.152:8080/video`
- Inference running with `yolov8n.pt` (placeholder model)
- Edge device appears on Dashboard and Map

### Edge config (`edge/config.yaml`)
```yaml
device_id: edge-01
mqtt:
  host: 10.86.85.6
  port: 8883
  tls:
    ca_cert: ./secrets/ca.crt
    client_cert: ./secrets/edge-01.crt
    client_key: ./secrets/edge-01.key
camera:
  source: http://10.86.85.152:8080/video
  fps: 30
location:
  lat: 15.628
  lon: 32.489
active_model: daylight-v1
model_profiles:
  - name: daylight-v1
    file_path: /home/mubarak/Project/UAV/UAV/yolov8n.pt
    camera_mode: daylight
signaling:
  url: ws://10.86.85.6:8090
```

---

## Key Fixes Applied

### Certs
- `certs/gen_certs.sh` — now includes IP SAN in server cert when `SERVER_IP` is set
- Server cert regenerated with `FORCE=1 SERVER_IP="10.86.85.6" DEVICE_IDS="edge-01" bash certs/gen_certs.sh`
- Mosquitto restarted after cert regeneration
- Cert files in `secrets/` are owned by `user` (not root) on main laptop

### Edge code
- `edge/main.py` — `CameraSource` now called with keyword args (`source=`, `fps=`, `frame_queue=`)
- `edge/inference_engine.py` — tracker fixed to `"bytetrack.yaml"` (was `"bytetrack"`)
- `edge/camera.py` — HTTP MJPEG parser added for IP Webcam (opencv-headless has no FFMPEG for HTTP)
- `launcher_edge.py` — runs `python -m edge.main` from project root (not `python main.py` from `edge/`), TLS cert path fields added to GUI, browse dialog handles `.crt`/`.key` files

### Docker / Main
- Mosquitto runs as root (`user: root` in compose) so it can read secrets volume
- Mosquitto has two listeners: 1883 plain (internal Docker) + 8883 TLS (external edge devices)
- Aggregation connects on port 1883 (no TLS needed internally)
- Frontend volume: builder copies dist to `/vol` on each start to avoid stale cache
- Tile server disabled — map uses internet OSM tiles
- All tkinter UI updates go through `after()` (thread safety, prevents GUI crashes)

---

## File Structure

```
.
├── edge/                  # Edge device Python inference stack
│   ├── main.py            # Entry point
│   ├── camera.py          # OpenCV + HTTP MJPEG capture
│   ├── inference_engine.py# YOLO + ByteTrack
│   ├── mqtt_client.py     # Publishes to MQTT
│   ├── command_handler.py # Handles commands from control center
│   ├── ptz_controller.py  # PTZ control (optional)
│   ├── sensor_reader.py   # Sensor polling (optional)
│   ├── estimator.py       # Distance/trajectory estimation (optional)
│   ├── webrtc_streamer.py # WebRTC live stream
│   ├── payload.py         # Payload dataclasses
│   └── config.py          # Config loader/validator
├── main/
│   ├── aggregation/       # FastAPI aggregation service
│   ├── control-center/    # FastAPI frontend proxy
│   └── signaling/         # Node.js WebRTC signaling
├── frontend/              # React/TypeScript control center UI
├── docker/                # Docker Compose + Mosquitto config
├── shared/schemas/        # JSON schemas for MQTT payloads
├── secrets/               # TLS certs (not in git, generate locally)
├── certs/gen_certs.sh     # Cert generation script
├── launcher_main.py       # Main device GUI launcher
├── launcher_edge.py       # Edge device GUI launcher
├── CONTEXT.md             # This file
└── EDGE_SETUP.md          # Edge device setup guide
```

---

## MQTT Topics

Edge publishes to:
- `uav/tracking/<device_id>` — detection results
- `uav/status/<device_id>` — online/offline heartbeat
- `uav/ptz/status/<device_id>` — PTZ position
- `uav/sensor/<device_id>` — sensor data

Edge subscribes to:
- `uav/command/<device_id>` — start/stop stream, switch model
- `uav/ptz/<device_id>` — PTZ commands

---

## Resuming Edge Device Work

```fish
# on edge laptop
git pull
python launcher_edge.py
```

Cert files are NOT in git — copy from main laptop if needed:
```fish
scp user@10.86.85.6:~/Projects/UAV/UAV/secrets/ca.crt ~/Projects/UAV/UAV/secrets/
scp user@10.86.85.6:~/Projects/UAV/UAV/secrets/edge-01.crt ~/Projects/UAV/UAV/secrets/
scp user@10.86.85.6:~/Projects/UAV/UAV/secrets/edge-01.key ~/Projects/UAV/UAV/secrets/
sudo chown user ~/Projects/UAV/UAV/secrets/*
chmod 600 ~/Projects/UAV/UAV/secrets/edge-01.key
chmod 644 ~/Projects/UAV/UAV/secrets/ca.crt ~/Projects/UAV/UAV/secrets/edge-01.crt
```
