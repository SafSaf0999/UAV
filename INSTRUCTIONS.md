# Anti-UAV Detection System — Setup & Run Instructions

## Hardware Setup

```
Phone (IP Webcam app)
  └── WiFi Hotspot
        ├── Main Laptop  (Docker stack, control center)
        └── Edge Laptop  (inference, connects to main via WiFi)
```

Both laptops connect to the **phone's WiFi hotspot**.  
The phone runs **IP Webcam** (Android) or **EpocCam / Camo** (iOS).

---

## 1. Prerequisites

### Both laptops (CachyOS)

```fish
# Install Python, Docker, ufw
sudo pacman -S python python-pip docker docker-compose ufw tk

# Enable Docker
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
# Log out and back in after this

# Enable UFW
sudo ufw enable
```

### Main laptop only

```fish
# Docker Compose is included with docker on Arch
docker compose version
```

### Edge laptop only

```fish
# Install Python deps for the edge device
pip install -r edge/requirements.txt

# If you don't have a GPU, OpenCV headless is fine (already in requirements.txt)
# For GPU inference (NVIDIA):
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

---

## 2. TLS Certificates (run once on main laptop)

```fish
cd certs
chmod +x gen_certs.sh

# Generate CA + server cert + one client cert for the edge device
DEVICE_IDS="edge-01" bash gen_certs.sh
```

This creates `secrets/ca.crt`, `secrets/server.crt/key`, `secrets/edge-01.crt/key`.

Copy the edge device certs to the edge laptop:

```fish
# From main laptop — replace <EDGE_IP> with the edge laptop's hotspot IP
scp secrets/ca.crt secrets/edge-01.crt secrets/edge-01.key user@<EDGE_IP>:~/uav-certs/
```

---

## 3. Phone — IP Webcam App

1. Install **IP Webcam** (Android) from Play Store.
2. Open the app → scroll down → tap **Start server**.
3. Note the URL shown, e.g. `http://192.168.43.1:8080`.
4. The video stream URL is: `http://192.168.43.1:8080/video`
5. The sensor URL is: `http://192.168.43.1:8080/sensors.json`

---

## 4. Main Laptop — Start the Stack

### Option A: GUI launcher (recommended)

```fish
python launcher_main.py
```

In the GUI:
- Set **MQTT Port** → `8883`
- Set **Control Center Port** → `8080`
- Set **Remote Access Mode** → `local`
- Click **Open Firewall Ports** (enters sudo password in terminal)
- Click **Start Stack**

The control center opens at `http://localhost:8080`.

### Option B: Terminal

```fish
cd docker
cp .env.example .env
# Edit .env if needed
docker compose up -d --build
```

Check services are up:

```fish
docker compose ps
```

---

## 5. Edge Laptop — Start Inference

### Option A: GUI launcher (recommended)

```fish
python launcher_edge.py
```

In the GUI:
- **Camera URL** → `http://192.168.43.1:8080/video`  
  *(replace with your phone's IP shown in IP Webcam)*
- **Main Device IP** → IP of the main laptop on the hotspot  
  *(run `ip addr` on main laptop, look for the hotspot interface, e.g. `192.168.43.x`)*
- **MQTT Port** → `8883`
- **Model .pt path** → browse to your `yolo26_*.pt` file
- **Active model name** → `daylight-v1` (or whatever you named it)
- **Device ID** → `edge-01`
- Click **Save Config**, then **Start Inference**

### Option B: Terminal

```fish
# Edit edge/config.yaml first
cp edge/config.example.yaml edge/config.yaml
nano edge/config.yaml   # or use any editor

# Set EDGE_CONFIG and run
set -x EDGE_CONFIG (pwd)/edge/config.yaml
python edge/main.py
```

---

## 6. Find the Main Laptop's Hotspot IP

On the **main laptop**, run:

```fish
ip addr show
```

Look for the interface connected to the phone hotspot (usually `wlan0` or `wlp*`).  
The IP will be something like `192.168.43.x`.

Use that IP as **Main Device IP** in the edge launcher.

---

## 7. Open the Control Center

On the **main laptop**, open a browser:

```
http://localhost:8080
```

You should see:
- **Dashboard** tab — edge-01 device listed as online
- **Map** tab — device marker at configured lat/lon
- **Live Feeds** tab — WebRTC stream from the phone camera
- **PTZ** tab — digital zoom controls

---

## 8. Firewall Ports Summary

| Port | Protocol | Service | Open on |
|------|----------|---------|---------|
| 8883 | TCP | MQTT broker (TLS) | Main laptop |
| 8080 | TCP | Control Center | Main laptop |
| 8090 | TCP | WebRTC Signaling | Main laptop |
| 8001 | TCP | Aggregation API | Main laptop |

The launchers handle `ufw allow` automatically. To do it manually:

```fish
# Main laptop
sudo ufw allow 8883/tcp
sudo ufw allow 8080/tcp
sudo ufw allow 8090/tcp
sudo ufw allow 8001/tcp
sudo ufw reload

# Edge laptop (usually no inbound ports needed)
sudo ufw reload
```

---

## 9. Stopping Everything

### Main laptop

```fish
# GUI: click Stop Stack
# or terminal:
cd docker && docker compose down
```

### Edge laptop

```fish
# GUI: click Stop
# or terminal: Ctrl+C in the terminal running python edge/main.py
```

---

## 10. Troubleshooting

**Edge can't connect to MQTT broker**
- Check the main laptop IP in `edge/config.yaml` → `mqtt.host`
- Verify port 8883 is open: `sudo ufw status`
- Check mosquitto logs: `docker compose logs mosquitto`

**Camera stream not working**
- Open `http://<phone_ip>:8080/video` in a browser on the edge laptop to verify
- Make sure both laptops are on the same hotspot network

**No detections showing**
- Verify the `.pt` model path in `edge/config.yaml` → `model_profiles[0].file_path`
- Check edge logs in the launcher output window

**Control center shows no devices**
- Check aggregation logs: `docker compose logs aggregation`
- Verify the edge device is publishing: look for `MQTT connected` in edge launcher output

**Docker permission denied**
```fish
sudo usermod -aG docker $USER
# Then log out and back in
```

---

## 11. Quick Reference — Key Files

| File | Purpose |
|------|---------|
| `launcher_main.py` | Main laptop GUI |
| `launcher_edge.py` | Edge laptop GUI |
| `edge/config.yaml` | Edge device config (auto-generated by GUI) |
| `docker/.env` | Main device Docker config (auto-generated by GUI) |
| `certs/gen_certs.sh` | TLS certificate generator |
| `secrets/` | Generated certs (never commit) |
| `edge/main.py` | Edge device entry point |
| `docker/docker-compose.yml` | Main device services |
