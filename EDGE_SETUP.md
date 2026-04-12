# Edge Device Setup (v3)

## Network

Both devices must be on the same network (phone hotspot, LAN, or WireGuard VPN).

| Device | Role |
|---|---|
| Main laptop | Docker stack, control center |
| Edge laptop | YOLO inference, MQTT publisher |
| Camera source | IP Webcam app, USB webcam, or RTSP stream |

---

## 1. Install dependencies

```fish
sudo pacman -S python python-pip tk
python -m venv .venv
source .venv/bin/activate.fish
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r edge/requirements.txt
```

For GPU inference (NVIDIA):
```fish
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

---

## 2. Get a model file

Use the recommended trained model (weights tracked in git via LFS):
```fish
# Already in the repo at:
UAV-dataset-workflow/training/finetuned/BirdDrone-2C/weights/best.pt
```

Or download a placeholder:
```fish
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
```

---

## 3. Copy TLS CA certificate from main laptop

v3 uses username/password MQTT auth — you only need the CA cert (no client certs).

```fish
mkdir -p ~/Project/UAV-2/UAV/secrets
scp user@<MAIN_IP>:~/Projects/UAV/UAV/secrets/ca.crt ~/Project/UAV-2/UAV/secrets/
chmod 644 ~/Project/UAV-2/UAV/secrets/ca.crt
```

---

## 4. Run the launcher

```fish
cd ~/Project/UAV-2/UAV
pkill -f edge.main   # kill any stale processes first
python launcher_edge.py
```

---

## 5. Configure in the launcher UI

| Field | Value |
|---|---|
| Camera URL | `http://<camera-ip>:8080/video` (IP Webcam) or `/dev/video0` (USB) |
| IP Webcam URL | `http://<phone-ip>:8080` (optional — enables remote camera controls) |
| Main Device IP | IP of the main laptop on the shared network |
| MQTT Port | `8883` |
| Username | `edge-01` (or your device ID) |
| Password | MQTT password set in `docker/.env` → `MQTT_PASSWORD_FILE` |
| Model .pt path | Path to `BirdDrone-2C-FT/weights/best.pt` |
| Active model name | `BirdDrone-2C-FT` |
| Device ID | `edge-01` |
| Latitude / Longitude | Your deployment coordinates |
| Signaling URL | `ws://<MAIN_IP>:8090` |

Click **Test Connection** to verify MQTT, **Preview Frame** to verify camera, then **Save Config** → **Start Inference**.

---

## 6. Verify connection

On the main laptop, open `http://localhost:8080` — the edge device should appear on the Dashboard and Map within a few seconds.

Check MQTT broker logs:
```fish
docker compose -f docker/docker-compose.yml logs mosquitto -f
```

A successful connection looks like:
```
New client connected from <EDGE_IP> as edge-01
```

---

## Regenerating certs (if main device IP changes)

Run on the main laptop:
```fish
FORCE=1 SERVER_IP="<MAIN_IP>" bash certs/gen_certs.sh
docker compose -f docker/docker-compose.yml restart mosquitto
scp secrets/ca.crt mubarak@<EDGE_IP>:~/Project/UAV-2/UAV/secrets/
```

---

## PTZ Follow (multi-device)

To make this edge device follow another device's detections, add to `edge/config.yaml`:
```yaml
ptz:
  enabled: true
  hardware_type: digital
  follow_leader: edge-01   # device_id of the leader
```

Test without hardware using the simulator:
```fish
python edge/edge_sim.py --host <MAIN_IP> --username edge-sim --password secret --device-id edge-sim
```
