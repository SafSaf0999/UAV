# Anti-UAV Detection System — Context Transfer

Paste this into a new Kiro chat to pick up where we left off.

---

## Project Summary

Full anti-UAV detection system. Two-laptop setup connected via phone WiFi hotspot.

- **Main laptop** (`10.196.175.6`) — Docker stack: MQTT broker, aggregation, signaling, web frontend, HA bridge
- **Edge laptop** (`10.196.175.187`) — Python inference via `launcher_edge.py`
- **Camera source** — IP Webcam app on phone, or any MJPEG/RTSP/USB source on the same network

OS: CachyOS (Arch-based), fish shell on both laptops.

---

## Trained Models (from UAV-dataset-workflow)

Four YOLO26s models trained and evaluated. **Recommended production model: BirdDrone-2C-FT.**

| Model | Classes | mAP@0.5 | mAP@0.5:0.95 | Weights path |
|---|---|---|---|---|
| BirdDrone-2C | Bird, Drone | 0.926 | 0.554 | `UAV-dataset-workflow/training/run_2class_yolo26s_rtx2070_100ep/weights/best.pt` |
| BirdDrone-3C | Bird, Drone, UAV | 0.892 | 0.574 | `UAV-dataset-workflow/training/run_3class_yolo26s_colab_t4_100ep/weights/best.pt` |
| BirdDrone-2C-FT | Bird, Drone | 0.969* | 0.678* | `UAV-dataset-workflow/training/finetuned/BirdDrone-2C/weights/best.pt` |
| BirdDrone-3C-FT | Bird, Drone, UAV | 0.881* | 0.598* | `UAV-dataset-workflow/training/finetuned/BirdDrone-3C/weights/best.pt` |

*On combined val set (original + DUT Anti-UAV pseudo-labels)

**Canonical classes:**
- `Bird` — confuser class (not a threat), shown in **green**
- `Drone` — threat (confidence ≥ 0.5 = **red**, < 0.5 = **orange**)
- `UAV` — large fixed-wing (3-class models only)

---

## Stack Status — Main Device

All Docker services managed via the **Anti-UAV Control Center** Electron desktop app (KDE application launcher) or `launcher_main.py`.

| Service | Port | Notes |
|---|---|---|
| mosquitto | 8883 (TLS, external) / 1883 (plain, internal) | MQTT broker, password auth |
| aggregation | 8001 (internal) | FastAPI, connects to MQTT on port 1883 |
| control-center | 8080 | Serves React frontend + JWT auth |
| signaling | 8090 (0.0.0.0) | WebRTC signaling — must be 0.0.0.0 for edge access |
| ha_bridge | — | Silent backend data bridge |
| tile-server | 8070 (optional) | Self-hosted OSM tiles — enable with `--profile tiles` |

Frontend at `http://localhost:8080` — "Anti-UAV Control Center" (v3)

**Auth (v3):**
- MQTT: username/password (no client certs needed)
- Web: JWT + invite tokens, sessions table, audit log
- Default admin: `admin` / `changeme` — change immediately

---

## Stack Status — Edge Device

Edge device at `10.196.175.187`.

### Edge config (`edge/config.yaml`)
```yaml
device_id: edge-01
mqtt:
  host: 10.196.175.6
  port: 8883
  username: edge-01
  password: <mqtt-password>
  tls:
    ca_cert: ./secrets/ca.crt
camera:
  source: http://<camera-ip>:8080/video
  fps: 15
location:
  lat: 15.628
  lon: 32.489
active_model: BirdDrone-2C-FT
model_profiles:
  - name: BirdDrone-2C-FT
    file_path: /path/to/UAV-dataset-workflow/training/finetuned/BirdDrone-2C/weights/best.pt
    camera_mode: daylight
    class_colors:
      Bird: "#22c55e"
      Drone: "#ef4444"
signaling:
  url: ws://10.196.175.6:8090
ipwebcam:
  url: http://<phone-ip>:8080   # optional — enables IP Webcam remote controls
```

---

## v3 Features (implemented)

- MQTT password auth (no more client certs to copy)
- Token management UI (Settings → Tokens)
- Session management UI (Settings → Sessions)
- Notification webhooks (Settings → Notifications)
- Per-device alert thresholds (Settings → Thresholds)
- Edge config push (Device Detail → Edit Config)
- Detection history export (Logs → Export Detections)
- Multi-device PTZ follow (`ptz.follow_leader` in edge config)
- Edge offline / health timeout detection (amber badge)
- IP Webcam remote controls (zoom, torch, ISO, exposure, snapshot, etc.)
- WebRTC black screen fix (last-frame fallback, wait for first frame)
- Bounding box colors: bird=green, drone≥50%=red, drone<50%=orange
- Electron desktop app (KDE application launcher)
- Self-hosted tile server (offline map, optional)

---

## Known Issues / Fixes Applied

### MQTT Auth (v3)
- Now uses username/password — no client certs needed on edge device
- Only `ca.crt` (server cert verification) needs to be copied to edge
- Generate: `FORCE=1 SERVER_IP="10.196.175.6" bash certs/gen_certs.sh`
- Copy CA only: `scp secrets/ca.crt mubarak@10.196.175.187:~/Project/UAV-2/UAV/secrets/`

### Offline Map (tile-server)
- Download region: `wget https://download.geofabrik.de/africa/sudan-latest.osm.pbf`
- Import: `docker compose -f docker/docker-compose.yml --profile tiles run --rm tile-server import`
- Start: `docker compose -f docker/docker-compose.yml --profile tiles up -d`
- Set in `.env`: `TILE_SERVER_URL=http://localhost:8070/{z}/{x}/{y}.png`

### Electron App
- Installed to KDE application launcher via `~/.local/share/applications/anti-uav-control-center.desktop`
- Close dialog: "Minimize to Tray" or "Shut Down" (stops all containers)
- Source: `UAV/electron/`

### Edge device
- Kill stale processes before starting: `pkill -f edge.main`
- Run from: `/home/mubarak/Project/UAV-2/UAV/`
- Venv: `/home/mubarak/Project/UAV-2/UAV/.venv/`

---

## File Structure

```
UAV/
├── edge/                  # Edge device Python inference stack
│   ├── main.py
│   ├── camera.py
│   ├── inference_engine.py
│   ├── mqtt_client.py     # username/password auth (primary)
│   ├── command_handler.py # update_config, ipwebcam_control, ipwebcam_sensors
│   ├── ipwebcam_handler.py# IP Webcam HTTP API proxy
│   ├── webrtc_streamer.py # WebRTC (black screen fix applied)
│   ├── health_reporter.py
│   ├── log_publisher.py
│   └── edge_sim.py        # Simulated edge device for PTZ follow testing
├── main/
│   ├── aggregation/       # FastAPI + detections DB + webhooks + thresholds
│   ├── control-center/    # FastAPI + JWT auth + sessions + tokens
│   ├── signaling/
│   └── ha_bridge/
├── frontend/              # React/TypeScript v3 UI
├── electron/              # Electron desktop app (AppImage + PKGBUILD)
├── docker/                # Docker Compose (tile-server enabled via --profile tiles)
├── secrets/               # TLS certs (NOT in git)
├── certs/gen_certs.sh     # Generates CA + server cert only (no client certs)
├── launcher_main.py       # Main device GUI launcher (tabbed, dark theme)
├── launcher_edge.py       # Edge device GUI launcher (tabbed, dark theme)
└── UAV-dataset-workflow/  # Dataset management + YOLO training toolkit
```

---

## MQTT Topics

| Topic | Direction | Description |
|---|---|---|
| `uav/tracking/{id}` | Edge → Main | Detection results per frame |
| `uav/status/{id}` | Edge → Main | Online/offline + model (retained) |
| `uav/health/{id}` | Edge → Main | CPU, memory, FPS, uptime |
| `uav/log/{id}` | Edge → Main | WARNING+ log entries |
| `uav/sensor/{id}` | Edge → Main | Compass bearing, pitch |
| `uav/ptz/status/{id}` | Edge → Main | PTZ position after command |
| `uav/ipwebcam/capabilities/{id}` | Edge → Main | IP Webcam available settings |
| `uav/ipwebcam/sensors/{id}` | Edge → Main | Battery, light, motion, etc. |
| `uav/snapshot/{id}` | Edge → Main | Base64 JPEG snapshot |
| `uav/command/{id}` | Main → Edge | start_stream, stop_stream, switch_model, update_config, ipwebcam_control, ipwebcam_sensors |
| `uav/ptz/{id}` | Main → Edge | pan, tilt, zoom, pan_to_bearing |
