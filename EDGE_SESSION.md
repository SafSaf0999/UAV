# Edge Device Session — Changes & Status (v3)

## What Changed in v3

### MQTT Authentication
- **Before**: TLS client certificates (ca.crt + edge-01.crt + edge-01.key)
- **After**: Username/password only — only `ca.crt` needed on edge device
- Edge config now uses `mqtt.username` and `mqtt.password` fields
- `mqtt_client.py` uses `username_pw_set()` as primary auth path

### Command Handler Additions
- `update_config` — live update camera source, FPS, active model without restart
- `ipwebcam_control` — proxy controls to IP Webcam HTTP API (zoom, torch, ISO, etc.)
- `ipwebcam_sensors` — fetch and publish phone sensor data

### New Files
- `edge/ipwebcam_handler.py` — IP Webcam HTTP API proxy with 5-min capability cache
- `edge/edge_sim.py` — simulated edge device for PTZ follow testing

### WebRTC Black Screen Fix
- `CameraVideoTrack._get_frame()` now returns last good frame when queue is empty
- `WebRTCStreamer._create_offer()` waits for first real frame before sending offer
- Frontend `useWebRTCStream` hook: `play()` called on `ontrack`, state transitions on `canplay`

---

## Current Config (edge/config.yaml)

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

---

## Current Status

- MQTT: username/password auth to main laptop on port 8883 with TLS
- Camera: IP Webcam or USB/RTSP source
- Inference: BirdDrone-2C-FT recommended (mAP@0.5=0.969, bird FA=0.3%)
- WebRTC: black screen fix applied — streams real frames immediately
- IP Webcam controls: available in Device Detail page when `ipwebcam.url` is set
- Edge device appears on Dashboard and Map at `http://localhost:8080`

---

## Resuming Edge Device Work

```fish
# On edge laptop
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
