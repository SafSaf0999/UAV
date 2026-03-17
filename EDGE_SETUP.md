# Edge Device Setup

## Network

| Device | IP |
|---|---|
| Main laptop | 10.86.85.6 |
| Edge laptop | 10.86.85.187 |
| Phone (hotspot + camera) | 10.86.85.152 |

---

## 1. Install dependencies

```fish
sudo pacman -S python python-pip tk
```

Install CPU-only torch first to avoid pulling 2GB+ of CUDA packages:

```fish
python -m venv .venv
source .venv/bin/activate.fish
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r edge/requirements.txt
```

---

## 2. Get a model file

If you don't have a UAV-specific model, use YOLOv8 nano as a placeholder:

```fish
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
```

This downloads `yolov8n.pt` to the current directory.

---

## 3. Copy TLS certificates from main laptop

Certs are not in git. Copy them over SSH:

```fish
mkdir -p ~/Projects/UAV/UAV/secrets
scp user@10.86.85.6:~/Projects/UAV/UAV/secrets/ca.crt ~/Projects/UAV/UAV/secrets/
scp user@10.86.85.6:~/Projects/UAV/UAV/secrets/edge-01.crt ~/Projects/UAV/UAV/secrets/
scp user@10.86.85.6:~/Projects/UAV/UAV/secrets/edge-01.key ~/Projects/UAV/UAV/secrets/
sudo chown user ~/Projects/UAV/UAV/secrets/*
chmod 600 ~/Projects/UAV/UAV/secrets/edge-01.key
chmod 644 ~/Projects/UAV/UAV/secrets/ca.crt ~/Projects/UAV/UAV/secrets/edge-01.crt
```

If SSH isn't enabled on the main laptop:
```fish
# on main laptop
sudo systemctl enable --now sshd
sudo ufw allow 22/tcp
```

---

## 4. Run the launcher

```fish
python launcher_edge.py
```

---

## 5. Configure in the launcher UI

| Field | Value |
|---|---|
| Camera URL | `http://10.86.85.152:8080/video` |
| FPS | `30` |
| Main Device IP | `10.86.85.6` |
| MQTT Port | `8883` |
| CA Cert path | `./secrets/ca.crt` |
| Client Cert path | `./secrets/edge-01.crt` |
| Client Key path | `./secrets/edge-01.key` |
| Model .pt path | path to `yolov8n.pt` |
| Active model name | `daylight-v1` |
| Device ID | `edge-01` |
| Latitude / Longitude | `15.628` / `32.489` |
| Signaling URL | `ws://10.86.85.6:8090` |

Click **Save Config** then **Start Inference**.

---

## 6. Verify connection

On the main laptop, open `http://localhost:8080` — the edge device should appear on the Dashboard and Map within a few seconds.

Check MQTT broker logs:
```fish
docker compose -f docker/docker-compose.yml logs mosquitto -f
```

A successful connection looks like:
```
New client connected from 10.86.85.187 as edge-01
```

---

## Regenerating certs (if needed)

Run on the main laptop from the project root:

```fish
FORCE=1 SERVER_IP="10.86.85.6" DEVICE_IDS="edge-01" bash certs/gen_certs.sh
docker compose -f docker/docker-compose.yml restart mosquitto
```

Then re-copy the certs to the edge laptop (step 3 above).
