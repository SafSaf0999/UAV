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

---

## Part 1 — Control Center (Main Device)

### Prerequisites

```bash
sudo pacman -S python python-pip docker docker-compose ufw tk nodejs npm
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
# Log out and back in after adding yourself to the docker group
sudo ufw enable
```

### Step 1 — Generate TLS Certificates (once)

```bash
# Replace with your main device's IP on the shared network
FORCE=1 SERVER_IP="<MAIN_DEVICE_IP>" bash certs/gen_certs.sh
```

This creates `secrets/ca.crt` and `secrets/server.crt/key`. No client certs needed.

Copy the CA cert to the edge device:
```bash
scp secrets/ca.crt user@<EDGE_IP>:~/path/to/UAV/secrets/
```

### Step 2 — Configure Environment

```bash
cp docker/.env.example docker/.env
```

Edit `docker/.env` — at minimum set:
```
MQTT_AUTH_MODE=password
MQTT_PASSWORD_FILE=/secrets/passwd
JWT_SECRET=<long-random-string>
BOOTSTRAP_ADMIN_PASSWORD=<your-password>
```

Create the MQTT password file:
```bash
# Install mosquitto-clients for mosquitto_passwd
sudo pacman -S mosquitto
mosquitto_passwd -c secrets/passwd edge-01
# Enter the password for the edge device
```

### Step 3 — Start the Stack

**Option A: Electron desktop app (recommended)**

Install once:
```bash
npm install --prefix electron
```

Add to KDE application launcher (already done if you ran the setup):
```bash
cp electron/anti-uav-control-center.desktop ~/.local/share/applications/
update-desktop-database ~/.local/share/applications/
```

Launch from KDE application launcher, or:
```bash
DISPLAY=:0 npm start --prefix electron
```

The app starts the Docker stack automatically, shows a loading screen, then opens the control center at `http://localhost:8080`.

**Close behaviour:** closing the window shows a dialog — "Minimize to Tray" keeps the stack running, "Shut Down" stops all containers.

**Option B: GUI launcher**
```bash
python launcher_main.py
```

**Option C: Terminal**
```bash
sudo docker compose -f docker/docker-compose.yml up -d --build
```

### Step 4 — First Login

Open `http://localhost:8080` in a browser.

- Username: `admin` (or value of `BOOTSTRAP_ADMIN_USERNAME` in `.env`)
- Password: `changeme` (or value of `BOOTSTRAP_ADMIN_PASSWORD` in `.env`)

**Change the password immediately** via Settings → Users → Generate Invite → create new admin → deactivate old.

### Step 5 — Offline Map (optional, one-time)

```bash
# Sudan tiles already downloaded to /tmp/sudan-latest.osm.pbf
# Import (takes 10-30 minutes):
sudo docker compose -f docker/docker-compose.yml --profile tiles run --rm \
  -v /tmp/sudan-latest.osm.pbf:/data/region.osm.pbf tile-server import

# Add to docker/.env:
echo "TILE_SERVER_URL=http://localhost:8070/{z}/{x}/{y}.png" >> docker/.env

# Restart with tile server:
sudo docker compose -f docker/docker-compose.yml --profile tiles up -d
```

---

## Part 2 — Edge Device

### Prerequisites

```bash
sudo pacman -S python python-pip tk
python -m venv .venv
source .venv/bin/activate.fish   # or: source .venv/bin/activate
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r edge/requirements.txt
```

For GPU inference (NVIDIA):
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

### Camera Source

Any of these work:
- **IP Webcam (Android)** — install from Play Store, tap Start Server, use `http://<phone-ip>:8080/video`
- **USB webcam** — set `camera.source: /dev/video0` in config
- **RTSP stream** — set `camera.source: rtsp://...` in config

### Model

The production model weights are in the repo (Git LFS):
```
UAV-dataset-workflow/training/finetuned/BirdDrone-2C/weights/best.pt
```

Or use a placeholder:
```bash
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
```

### Start Inference

```bash
pkill -f edge.main   # kill stale processes first
python launcher_edge.py
```

In the launcher:
- **Camera URL** → your camera stream URL
- **Main Device IP** → IP of the main device on the shared network
- **MQTT Username** → `edge-01` (or your device ID)
- **MQTT Password** → password set in `secrets/passwd` on the main device
- **Model .pt path** → path to `BirdDrone-2C-FT/weights/best.pt`
- **Device ID** → `edge-01`

Click **Test Connection** to verify MQTT, **Preview Frame** to verify camera, then **Save Config** → **Start Inference**.

---

## Part 3 — Dataset Workflow & Training

Located in `UAV-dataset-workflow/`. A PyQt5 desktop app + CLI for managing datasets and training YOLO26s models.

### Setup

```bash
cd UAV-dataset-workflow
python -m venv .venv
source .venv/bin/activate.fish
pip install -e ".[dev]"
```

### Launch

```bash
python launch.py          # interactive menu
python launch.py --gui    # full launcher GUI
anti-uav                  # if installed via pip
```

### Pipeline

```
1. Inspect    → scan dataset, detect annotation format, compute stats
2. Review     → browse images, curate labels, remap classes
3. Normalize  → remap all labels to canonical classes (Bird / Drone)
4. Merge      → combine datasets, deduplicate by SHA-256
5. Train      → YOLO26s training (RTX 2070 / Colab T4 profiles)
6. Document   → auto-generate per-run Markdown docs
7. Evaluate   → DUT Anti-UAV video-level detection analysis
```

---

## Firewall Ports (Main Device)

| Port | Service |
|------|---------|
| 8883 | MQTT broker (TLS) — edge devices |
| 8080 | Control center web UI |
| 8090 | WebRTC signaling — edge devices |

Port 8070 (tile server) is local only — no firewall rule needed.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Edge not appearing on dashboard | `sudo docker compose logs aggregation` |
| MQTT auth failed | Check username/password in edge config matches `secrets/passwd` |
| MQTT TLS error | Regenerate certs with correct `SERVER_IP`, copy `ca.crt` to edge |
| Live feed black / waiting | Start camera source first, then click Stream |
| Camera test fails (no cv2) | Run from `.venv/bin/python3`, not system python |
| Login fails | Check `BOOTSTRAP_ADMIN_PASSWORD` in `docker/.env` |
| Map not loading offline | Run tile server import first |
| Electron hangs on startup | Docker daemon not running: `sudo systemctl start docker` |
| Edge device amber badge | Health timeout — edge process crashed, restart it |
| Docker permission denied | `sudo usermod -aG docker $USER` then re-login |
