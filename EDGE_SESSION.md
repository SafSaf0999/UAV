# Edge Device Session Notes

## Current Status

- **Main device:** `10.196.175.6`
- **Edge device:** `10.196.175.187` (username: `mubarak`)
- **Camera:** IP Webcam on phone (same network)
- **Auth:** MQTT username/password (no client certs)
- **Model:** BirdDrone-2C-FT (recommended) or yolov8n.pt (placeholder)

## Resuming Edge Device

```fish
# On edge device
pkill -f edge.main
cd /home/mubarak/Project/UAV-2/UAV
python launcher_edge.py
```

Or headless:
```fish
set -x EDGE_CONFIG (pwd)/edge/config.yaml
set -x YOLO_AUTOINSTALL false
.venv/bin/python -m edge.main
```

## SSH from main device

```fish
ssh mubarak@10.196.175.187
```

## Key changes since initial setup

- MQTT now uses username/password auth — no client certs needed on edge
- Only `ca.crt` needs to be in `secrets/` on the edge device
- `launcher_edge.py` has tabbed UI (Config / Status / Logs) with dark theme
- IP Webcam controls available in Device Detail page when `ipwebcam.url` is set in config
- WebRTC black screen fix applied — streams real frames immediately
- `edge_sim.py` available for PTZ follow testing without hardware

## Current edge/config.yaml

```yaml
device_id: edge-01
mqtt:
  host: 10.196.175.6
  port: 8883
  username: edge-01
  password: <set in launcher>
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
    file_path: /path/to/training/finetuned/BirdDrone-2C/weights/best.pt
    camera_mode: daylight
signaling:
  url: ws://10.196.175.6:8090
ipwebcam:
  url: http://<phone-ip>:8080   # optional
```
