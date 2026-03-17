# Edge Device Session — Changes & Status

## What Was Done

### 1. Python venv + dependencies
CPU-only torch must be installed first to avoid pulling CUDA packages (2GB+):
```bash
python -m venv .venv
source .venv/bin/activate.fish  # or .venv/bin/activate for bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r edge/requirements.txt
```

### 2. TLS — server cert missing IP SAN
The original `certs/gen_certs.sh` didn't include a Subject Alternative Name for the broker IP.
The script was updated to support a `SERVER_IP` env var that adds `IP:<addr>` to the SAN.

The server cert was manually regenerated on the main laptop:
```bash
cd ~/Projects/UAV/UAV/secrets
echo "subjectAltName=DNS:localhost,IP:10.86.85.6" > san.ext
openssl req -new -key server.key -out server.csr -subj "/CN=localhost/O=AntiUAV/OU=Broker"
openssl x509 -req -days 3650 -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial -extfile san.ext -out server.crt
rm server.csr san.ext
```

Then mosquitto was restarted:
```bash
cd ~/Projects/UAV/UAV/docker
docker compose restart mosquitto
```

For future cert regeneration use:
```bash
FORCE=1 SERVER_IP="10.86.85.6" DEVICE_IDS="edge-01" bash certs/gen_certs.sh
```

### 3. Code fixes

**`edge/main.py`** — `CameraSource` was called with wrong arguments:
```python
# Before
camera = CameraSource(config, frame_queue)
# After
camera = CameraSource(
    source=config.get("camera.source"),
    fps=int(config.get("camera.fps", 15)),
    frame_queue=frame_queue,
)
```

**`edge/inference_engine.py`** — wrong tracker name:
```python
# Before
tracker="bytetrack"
# After
tracker="bytetrack.yaml"
```

**`edge/camera.py`** — added MJPEG-over-HTTP support for IP Webcam (opencv-python-headless has no FFMPEG for HTTP URLs). HTTP sources now use a manual JPEG boundary parser instead of `cv2.VideoCapture`.

**`launcher_edge.py`** — multiple fixes:
- Runs `python -m edge.main` from project root (not `python main.py` from `edge/`)
- Added TLS cert path fields (CA cert, client cert, client key) to the GUI and config builder
- Added scrollable canvas so the window fits small screens
- Browse dialog supports `.crt`/`.key` files

---

## Current Config (edge/config.yaml)

```yaml
device_id: edge-01
mqtt:
  host: 10.86.85.6   # main laptop hotspot IP
  port: 8883
  tls:
    ca_cert: ./secrets/ca.crt
    client_cert: ./secrets/edge-01.crt
    client_key: ./secrets/edge-01.key
camera:
  source: http://10.86.85.152:8080/video  # phone IP Webcam
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

## Current Status

- MQTT: connected to main laptop on port 8883 with TLS
- Camera: phone IP Webcam at `http://10.86.85.152:8080/video` — working
- Inference: running with `yolov8n.pt` (placeholder model)
- WebRTC live feed: streamer starts on `start_stream` MQTT command from frontend
- Edge device appears on Dashboard and Map at `http://localhost:8080`

---

## Main Laptop — Required Actions

If certs were regenerated, copy updated certs back to edge device:
```bash
scp secrets/ca.crt secrets/edge-01.crt secrets/edge-01.key mubarak@<EDGE_IP>:~/Project/UAV/UAV/secrets/
```

Verify mosquitto has the correct server cert:
```bash
openssl x509 -in secrets/server.crt -noout -text | grep -A2 "Subject Alternative"
# Should show: DNS:localhost, IP Address:10.86.85.6
```
