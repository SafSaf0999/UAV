# Anti-UAV Detection System

Real-time UAV/drone detection and tracking system with a web-based control center and a dataset management + training toolkit.

```
Phone (WiFi Hotspot + IP Webcam)
        │
        ├── Main Laptop  ←── Docker stack (MQTT, aggregation, control center)
        └── Edge Laptop  ←── YOLO inference, publishes detections via MQTT
```

---

## Repository Structure

```
UAV/                          ← Control center (this repo root)
├── edge/                     ← Edge device inference stack
├── main/                     ← Backend services (aggregation, auth, signaling, bridge)
├── frontend/                 ← React/TypeScript control center UI
├── docker/                   ← Docker Compose + Mosquitto config
├── certs/gen_certs.sh        ← TLS certificate generator
├── secrets/                  ← Generated certs (not in git — generate locally)
├── launcher_main.py          ← Main laptop GUI launcher
├── launcher_edge.py          ← Edge laptop GUI launcher
└── UAV-dataset-workflow/     ← Dataset management + YOLO training toolkit
```

---

## Part 1 — Control Center

### Prerequisites

**Both laptops** (Arch/CachyOS):

```bash
sudo pacman -S python python-pip docker docker-compose ufw tk
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
# Log out and back in after adding yourself to the docker group
```

**Edge laptop only** — create a venv and install Python deps:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r edge/requirements.txt
```

For GPU inference (NVIDIA):

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

---

### Step 1 — Generate TLS Certificates (main laptop, once)

```bash
# Replace 10.202.14.6 with your main laptop's IP on the hotspot
FORCE=1 SERVER_IP="10.202.14.6" DEVICE_IDS="edge-01" bash certs/gen_certs.sh
```

This creates `secrets/ca.crt`, `secrets/server.crt/key`, `secrets/edge-01.crt/key`.

Copy the edge certs to the edge laptop:

```bash
scp secrets/ca.crt secrets/edge-01.crt secrets/edge-01.key user@<EDGE_IP>:~/path/to/UAV/secrets/
```

---

### Step 2 — Phone Setup

1. Install **IP Webcam** (Android, Play Store)
2. Open the app → scroll down → tap **Start server**
3. Note the URL shown, e.g. `http://10.202.14.184:8080`
4. Video stream URL: `http://10.202.14.184:8080/video`

---

### Step 3 — Start the Main Stack

**Option A: GUI launcher (recommended)**

```bash
python launcher_main.py
```

- Set MQTT Port → `8883`, Control Center Port → `8080`
- Click **Open Firewall Ports**, then **Start Stack**
- Control center opens at `http://localhost:8080`

**Option B: Terminal**

```bash
cp docker/.env.example docker/.env
# Edit docker/.env if needed (admin credentials, JWT secret, etc.)
docker compose -f docker/docker-compose.yml up -d --build
```

**First login credentials** (change immediately after first login):

```
Username: admin
Password: changeme
```

Change via Settings → Users → Generate Invite → create new admin → deactivate old.

---

### Step 4 — Start the Edge Device

On the edge laptop:

```bash
# Kill any stale processes first
pkill -f edge.main

python launcher_edge.py
```

In the GUI:
- **Camera URL** → `http://<phone-ip>:8080/video`
- **Main Device IP** → IP of the main laptop on the hotspot
- **Model .pt path** → path to your trained weights (e.g. BirdDrone-2C-FT)
- **Device ID** → `edge-01`
- Click **Save Config** → **Start Inference**

**To use the recommended trained model**, set the model path to:

```
UAV-dataset-workflow/training/finetuned/BirdDrone-2C/weights/best.pt
```

---

### Step 5 — Open the Control Center

```
http://localhost:8080        ← from main laptop
http://<main-ip>:8080        ← from any device on the same network
```

**Pages:**
- **Overview** — device cards with detection counts, health, uptime
- **Map** — live device markers, click for slide-in panel with live feed + PTZ
- **Live Feeds** — up to 4 simultaneous WebRTC streams with bounding box overlay
- **Devices** — full device list
- **Logs** — WARNING+ log stream from all edge devices, filterable, CSV export
- **Settings** — theme, user management, invite tokens, audit log (admin only)

---

### Firewall Ports (main laptop)

| Port | Service |
|------|---------|
| 8883 | MQTT broker (TLS) |
| 8080 | Control center web UI |
| 8090 | WebRTC signaling |

---

### Install as Android App (PWA)

1. Connect Android to the same network as the main laptop
2. Open Chrome → navigate to `http://<main-ip>:8080`
3. Log in → tap ⋮ → **Add to Home Screen**
4. Launches fullscreen with the UAV radar icon

---

### Auth & Invite Tokens

- Roles: `admin` (full access) | `viewer` (read-only, no commands)
- Invite tokens: `UAV-XXXX-XXXX` format, up to 30 days expiry
- New users visit `/register?token=UAV-XXXX-XXXX` to create an account
- Every PTZ/command action is written to the audit log with username + timestamp

---

### Trained Models

| Model | Classes | mAP@0.5 | mAP@0.5:0.95 | Notes |
|---|---|---|---|---|
| BirdDrone-2C | Bird, Drone | 0.926 | 0.554 | Base 2-class |
| BirdDrone-3C | Bird, Drone, UAV | 0.892 | 0.574 | Base 3-class |
| BirdDrone-2C-FT | Bird, Drone | 0.969 | 0.678 | **Recommended** |
| BirdDrone-3C-FT | Bird, Drone, UAV | 0.881 | 0.598 | Fine-tuned 3-class |

Weights are in `UAV-dataset-workflow/training/` (not tracked in git — large files).

---

### Troubleshooting

| Symptom | Fix |
|---------|-----|
| Edge not appearing on dashboard | Check `docker compose logs aggregation` |
| MQTT TLS error on edge | Regenerate certs with correct `SERVER_IP`, restart mosquitto |
| Live feed black / waiting | Start IP Webcam on phone first, then click Stream |
| Camera test fails (no module cv2) | Run from `.venv/bin/python3`, not system python |
| Login fails | Check `BOOTSTRAP_ADMIN_PASSWORD` in `docker/.env` |
| Docker permission denied | `sudo usermod -aG docker $USER` then re-login |

---

## Part 2 — Dataset Workflow & Training

Located in `UAV-dataset-workflow/`. A PyQt5 desktop app + CLI for managing anti-UAV datasets and training YOLO26 models.

### Prerequisites

```bash
python -m venv .venv
source .venv/bin/activate      # fish: source .venv/bin/activate.fish
pip install -e ".[dev]"
```

Requires Python 3.10+.

---

### Launching the GUI

**Option A: Unified launcher script**

```bash
python UAV-dataset-workflow/launch.py
```

This opens an interactive menu listing all available datasets with image counts. Select a number to open the image reviewer for that dataset, or `0` to open the full launcher GUI.

You can also pass a dataset name directly:

```bash
python UAV-dataset-workflow/launch.py uavs
python UAV-dataset-workflow/launch.py --gui    # full launcher directly
```

**Option B: CLI entry point** (after `pip install -e .`)

```bash
anti-uav                          # full launcher GUI
anti-uav inspect <dataset_path>   # inspect a dataset
anti-uav review <dataset_path>    # open image reviewer
anti-uav normalize <path> --mapping mapping.json
anti-uav merge
anti-uav train --profile rtx2070
anti-uav document <run_dir>
anti-uav compare
```

---

### GUI Workflow

```
1. Inspect    → scan dataset folder, detect annotation format, compute stats
2. Review     → browse images, curate labels, remap classes via hover-preview GUI
3. Normalize  → remap all source labels to canonical classes (Bird / Drone / UAV)
4. Merge      → combine datasets, deduplicate by SHA-256, write data.yaml
5. Train      → YOLO26 training with hardware profiles (RTX 2070 / Colab T4)
6. Document   → auto-generate per-run Markdown docs and comparison reports
7. Evaluate   → DUT Anti-UAV video-level detection analysis with annotated MP4 output
```

---

### Class Mapping

Two canonical class sets are supported:

- **2-class** (`mapping_2class.json`): `Bird`, `Drone`
- **3-class** (`mapping.json`): `Bird`, `Drone`, `UAV`

---

### Training Profiles

| Profile | Hardware | Batch | Notes |
|---------|----------|-------|-------|
| `rtx2070` | NVIDIA RTX 2070 8 GB | 16 | Local training |
| `colab_t4` | Google Colab T4 | 32 | Remote, semi-automated |
| `kaggle` | Kaggle P100 | 32 | Remote, fully automated via API |

---

### Dataset Structure Expected

```
datasets/
  <dataset-name>/
    train/
      images/   ← .jpg / .png
      labels/   ← YOLO .txt annotations
    valid/
      images/
      labels/
```

---

### Full Documentation

See `UAV-dataset-workflow/documentations/` for:
- `report_full.pdf` — full scientific report (methodology, results, discussion)
- `citations.md` — dataset citation requirements
- Per-run training graphs and comparison reports
