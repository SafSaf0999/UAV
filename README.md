# Anti-UAV Detection System

Real-time distributed UAV/drone detection using YOLO26s on edge devices with a centralised web-based control center.

```
Camera Source (IP Webcam / USB / RTSP) — same network
        │
        ├── Main Device  ←── Docker stack (MQTT, aggregation, control center)
        └── Edge Device  ←── YOLO inference, publishes detections via MQTT
```

**Full documentation:** see `PROJECT.md`

---

## Quick Start

### Main Device

**Option A — Desktop app (recommended)**

Install Node dependencies once:
```bash
npm install --prefix electron
```

Then launch from the KDE application launcher, or:
```bash
DISPLAY=:0 npm start --prefix electron
```

**Option B — Terminal**
```bash
cp docker/.env.example docker/.env
# Edit docker/.env
sudo docker compose -f docker/docker-compose.yml up -d --build
```

Open `http://localhost:8080` — default login: `admin` / `changeme`

### Edge Device

```bash
python -m venv .venv
source .venv/bin/activate   # fish: source .venv/bin/activate.fish
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r edge/requirements.txt

# Copy CA cert from main device
scp user@<MAIN_IP>:~/path/to/UAV/secrets/ca.crt ./secrets/

# Start
python launcher_edge.py
```

---

## Production Model

**BirdDrone-2C-FT** — YOLO26s fine-tuned on DUT Anti-UAV benchmark

| Metric | Value |
|---|---|
| mAP@0.5 | 0.969 |
| mAP@0.5:0.95 | 0.678 |
| Bird false alarm rate | 0.3% |
| DUT detection rate | 0.818 |

Weights: `UAV-dataset-workflow/training/finetuned/BirdDrone-2C/weights/best.pt` (tracked via Git LFS)

---

## Docker Services

| Service | Port | Role |
|---|---|---|
| mosquitto | 8883 / 1883 | MQTT broker (TLS+password external, plain internal) |
| aggregation | 8001 | FastAPI — device state, WebSocket, detection DB |
| control-center | 8080 | FastAPI — UI, JWT auth, API proxy |
| signaling | 8090 | Node.js WebRTC signaling |
| ha_bridge | — | Silent backend bridge |
| tile-server | 8070 | Offline OSM tiles (`--profile tiles`) |

---

## Key Features

- **YOLO26s inference** on edge devices with ByteTrack multi-object tracking
- **Real-time dashboard** with per-class detection color coding (bird=green, drone=red/orange)
- **Interactive map** with device markers and slide-in detail panel
- **WebRTC live feeds** — up to 4 simultaneous streams with bounding box overlay
- **IP Webcam remote controls** — zoom, torch, ISO, exposure, snapshot via edge proxy
- **Multi-device PTZ follow** — automatic bearing computation from detections
- **JWT authentication** with invite tokens, session management, audit trail
- **Notification webhooks** — HMAC-signed HTTP callbacks for detection/online/offline events
- **Per-device alert thresholds** — configurable confidence, consecutive frames, alert classes
- **Detection history export** — CSV download with date range filter
- **Offline map** — self-hosted OSM tile server (Sudan tiles pre-imported)
- **Electron desktop app** — KDE launcher entry, tray icon, auto-manages Docker stack

---

## Dataset Workflow

```bash
python UAV-dataset-workflow/launch.py        # interactive menu
python UAV-dataset-workflow/launch.py --gui  # full launcher GUI
```

See `UAV-dataset-workflow/README.md` for the full ML pipeline documentation.

---

## Report

`report_full.pdf` — 56-page academic report covering methodology, training, evaluation, and system architecture.
