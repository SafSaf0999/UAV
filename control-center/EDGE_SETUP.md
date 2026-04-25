# Edge Device Setup

See `PROJECT.md` Section 8 for the full edge config reference.

## Quick Setup

### 1. Install dependencies

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

### 2. Get the production model

The model weights are tracked in the repo via Git LFS:
```
UAV-dataset-workflow/training/finetuned/BirdDrone-2C/weights/best.pt
```

Or use a placeholder:
```fish
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
```

### 3. Copy CA certificate from main device

Only the CA cert is needed (no client certs since v3 uses password auth):

```fish
mkdir -p ~/Project/UAV-2/UAV/secrets
scp user@<MAIN_IP>:~/Projects/UAV/UAV/secrets/ca.crt ~/Project/UAV-2/UAV/secrets/
chmod 644 ~/Project/UAV-2/UAV/secrets/ca.crt
```

### 4. Run the launcher

```fish
pkill -f edge.main   # kill stale processes first
python launcher_edge.py
```

In the launcher:
- Set camera URL, main device IP, MQTT username/password, model path
- Click **Test Connection** to verify MQTT
- Click **Preview Frame** to verify camera
- Click **Save Config** → **Start Inference**

### 5. Verify

On the main device, open `http://localhost:8080` — the edge device should appear on the Dashboard and Map within a few seconds.

## Regenerating certs (if main device IP changes)

```fish
# On main device
FORCE=1 SERVER_IP="<NEW_IP>" bash certs/gen_certs.sh
sudo docker compose -f docker/docker-compose.yml restart mosquitto
scp secrets/ca.crt mubarak@<EDGE_IP>:~/Project/UAV-2/UAV/secrets/
```
