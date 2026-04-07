#!/usr/bin/env python3
"""
Anti-UAV Detection — Edge Device Launcher
Simplified GUI: 3 primary fields, collapsible Advanced section,
Test Camera and Test MQTT buttons.
"""

import os
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, font as tkfont, scrolledtext

import yaml

VENV_PYTHON = os.path.join(os.path.dirname(__file__), ".venv", "bin", "python3")
# Fall back to system python if venv doesn't exist yet
PYTHON = VENV_PYTHON if os.path.exists(VENV_PYTHON) else "python3"

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "edge", "config.yaml")
EXAMPLE_PATH = os.path.join(os.path.dirname(__file__), "edge", "config.example.yaml")
SECRETS_DIR = os.path.join(os.path.dirname(__file__), "secrets")

BG = "#0f172a"; CARD = "#1e293b"; ACC = "#3b82f6"; FG = "#f1f5f9"; DIM = "#94a3b8"
GREEN = "#22c55e"; RED = "#ef4444"; AMBER = "#f59e0b"

DEFAULTS = {
    "device_id": "edge-01",
    "mqtt_host": "10.42.0.1",
    "mqtt_port": "8883",
    "ca_cert": "./secrets/ca.crt",
    "client_cert": "./secrets/edge-01.crt",
    "client_key": "./secrets/edge-01.key",
    "camera_source": "http://10.202.184.184:8080/video",
    "camera_fps": "15",
    "model_path": "",
    "active_model": "daylight-v1",
    "lat": "0.0",
    "lon": "0.0",
    "ptz_enabled": "false",
    "ptz_type": "digital",
    "sensor_enabled": "false",
    "sensor_url": "http://10.202.184.184:8080/sensors.json",
    "estimator_enabled": "false",
    "signaling_url": "ws://10.42.0.1:8090",
}


def load_config():
    path = CONFIG_PATH if os.path.exists(CONFIG_PATH) else EXAMPLE_PATH
    try:
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def build_config(v):
    return {
        "device_id": v["device_id"],
        "mqtt": {
            "host": v["mqtt_host"],
            "port": int(v["mqtt_port"]),
            "tls": {
                "ca_cert": v["ca_cert"],
                "client_cert": v["client_cert"],
                "client_key": v["client_key"],
            },
        },
        "camera": {"source": v["camera_source"], "fps": int(v["camera_fps"])},
        "location": {"lat": float(v["lat"]), "lon": float(v["lon"])},
        "active_model": v["active_model"],
        "model_profiles": [{"name": v["active_model"], "file_path": v["model_path"], "camera_mode": "daylight"}] if v["model_path"] else [],
        "signaling": {"url": v["signaling_url"]},
        "ptz": {"enabled": v["ptz_enabled"].lower() == "true", "hardware_type": v["ptz_type"]},
        "sensor": {"enabled": v["sensor_enabled"].lower() == "true", "source": "http", "http_url": v["sensor_url"], "poll_interval_s": 1.0},
        "estimator": {"enabled": v["estimator_enabled"].lower() == "true", "fov_deg": 60.0, "reference_size_m": 0.5, "window_frames": 10},
    }


def save_config(v):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(build_config(v), f, default_flow_style=False, sort_keys=False)


def _auto_detect_certs(device_id):
    """Return cert paths if they exist in secrets/."""
    ca = os.path.join(SECRETS_DIR, "ca.crt")
    crt = os.path.join(SECRETS_DIR, f"{device_id}.crt")
    key = os.path.join(SECRETS_DIR, f"{device_id}.key")
    if os.path.exists(ca) and os.path.exists(crt) and os.path.exists(key):
        return f"./secrets/ca.crt", f"./secrets/{device_id}.crt", f"./secrets/{device_id}.key"
    return None, None, None


class EdgeLauncher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Anti-UAV — Edge Device Launcher")
        self.configure(bg=BG)
        self.resizable(True, True)
        self._proc = None
        self._build_ui()

    def _build_ui(self):
        label_font = tkfont.Font(family="monospace", size=10)
        btn_font = tkfont.Font(family="monospace", size=10, weight="bold")
        sec_font = tkfont.Font(family="monospace", size=10, weight="bold")

        tk.Label(self, text="Anti-UAV Detection — Edge Device",
                 bg=BG, fg=FG, font=tkfont.Font(family="monospace", size=13, weight="bold")).pack(pady=(14, 2))
        tk.Label(self, text="Configure camera, MQTT, and model, then start inference.",
                 bg=BG, fg=DIM, font=label_font).pack(pady=(0, 8))

        raw = load_config()
        self._vars = {k: tk.StringVar(value=v) for k, v in DEFAULTS.items()}

        # Pre-fill from existing config
        if raw:
            self._vars["device_id"].set(raw.get("device_id", DEFAULTS["device_id"]))
            self._vars["mqtt_host"].set(raw.get("mqtt", {}).get("host", DEFAULTS["mqtt_host"]))
            self._vars["mqtt_port"].set(str(raw.get("mqtt", {}).get("port", DEFAULTS["mqtt_port"])))
            tls = raw.get("mqtt", {}).get("tls", {})
            self._vars["ca_cert"].set(tls.get("ca_cert", DEFAULTS["ca_cert"]))
            self._vars["client_cert"].set(tls.get("client_cert", DEFAULTS["client_cert"]))
            self._vars["client_key"].set(tls.get("client_key", DEFAULTS["client_key"]))
            self._vars["camera_source"].set(raw.get("camera", {}).get("source", DEFAULTS["camera_source"]))
            self._vars["camera_fps"].set(str(raw.get("camera", {}).get("fps", DEFAULTS["camera_fps"])))
            self._vars["active_model"].set(raw.get("active_model", DEFAULTS["active_model"]))
            self._vars["lat"].set(str(raw.get("location", {}).get("lat", DEFAULTS["lat"])))
            self._vars["lon"].set(str(raw.get("location", {}).get("lon", DEFAULTS["lon"])))
            self._vars["signaling_url"].set(raw.get("signaling", {}).get("url", DEFAULTS["signaling_url"]))
            profiles = raw.get("model_profiles", [])
            if profiles:
                self._vars["model_path"].set(profiles[0].get("file_path", ""))

        # Auto-detect certs
        device_id = self._vars["device_id"].get()
        ca, crt, key = _auto_detect_certs(device_id)
        if ca:
            self._vars["ca_cert"].set(ca)
            self._vars["client_cert"].set(crt)
            self._vars["client_key"].set(key)

        def section(title):
            f = tk.Frame(self, bg=CARD, padx=14, pady=8)
            f.pack(fill="x", padx=16, pady=3)
            tk.Label(f, text=title, bg=CARD, fg=ACC, font=sec_font, anchor="w").grid(
                row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))
            return f

        def row(parent, r, label, key, browse=False):
            tk.Label(parent, text=label + ":", bg=CARD, fg=DIM, font=label_font,
                     anchor="w", width=20).grid(row=r, column=0, sticky="w", pady=2)
            e = tk.Entry(parent, textvariable=self._vars[key], bg=BG, fg=FG,
                         insertbackground=FG, font=label_font, relief="flat", width=32)
            e.grid(row=r, column=1, sticky="ew", padx=(8, 0), pady=2)
            if browse:
                tk.Button(parent, text="…", bg="#334155", fg=FG, font=label_font,
                          relief="flat", padx=4, command=lambda k=key: self._browse(k)).grid(
                    row=r, column=2, padx=(4, 0))
            parent.columnconfigure(1, weight=1)

        # Primary fields
        primary = section("Primary")
        row(primary, 1, "Camera URL", "camera_source")
        row(primary, 2, "Main Device IP", "mqtt_host")
        row(primary, 3, "Model .pt path", "model_path", browse=True)

        # Advanced toggle
        self._adv_visible = tk.BooleanVar(value=False)
        adv_btn = tk.Button(self, text="▶ Advanced", bg=BG, fg=DIM, font=label_font,
                            relief="flat", anchor="w", command=self._toggle_advanced)
        adv_btn.pack(fill="x", padx=16)
        self._adv_btn = adv_btn

        # Advanced section (hidden by default)
        self._adv_container = tk.Frame(self, bg=BG)

        adv_mqtt = section("MQTT / TLS")
        adv_mqtt.pack_forget()  # will be re-packed into adv_container
        row(adv_mqtt, 1, "MQTT Port", "mqtt_port")
        row(adv_mqtt, 2, "CA Cert", "ca_cert", browse=True)
        row(adv_mqtt, 3, "Client Cert", "client_cert", browse=True)
        row(adv_mqtt, 4, "Client Key", "client_key", browse=True)

        adv_device = section("Device")
        adv_device.pack_forget()
        row(adv_device, 1, "Device ID", "device_id")
        row(adv_device, 2, "Active Model Name", "active_model")
        row(adv_device, 3, "FPS", "camera_fps")
        row(adv_device, 4, "Latitude", "lat")
        row(adv_device, 5, "Longitude", "lon")
        row(adv_device, 6, "Signaling URL", "signaling_url")

        adv_opt = section("Optional")
        adv_opt.pack_forget()
        row(adv_opt, 1, "PTZ Enabled", "ptz_enabled")
        row(adv_opt, 2, "PTZ Type", "ptz_type")
        row(adv_opt, 3, "Sensor Enabled", "sensor_enabled")
        row(adv_opt, 4, "Sensor URL", "sensor_url")
        row(adv_opt, 5, "Estimator Enabled", "estimator_enabled")

        self._adv_sections = [adv_mqtt, adv_device, adv_opt]

        # Buttons
        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack(fill="x", padx=16, pady=8)

        tk.Button(btn_frame, text="Save Config", bg="#475569", fg=FG, font=btn_font,
                  relief="flat", padx=10, pady=6, command=self._save).pack(side="left", padx=(0, 6))

        self._start_btn = tk.Button(btn_frame, text="▶ Start Inference", bg=ACC, fg="#fff",
                                    font=btn_font, relief="flat", padx=12, pady=6, command=self._start)
        self._start_btn.pack(side="left", padx=(0, 6))

        self._stop_btn = tk.Button(btn_frame, text="■ Stop", bg=RED, fg="#fff",
                                   font=btn_font, relief="flat", padx=12, pady=6,
                                   command=self._stop, state="disabled")
        self._stop_btn.pack(side="left", padx=(0, 6))

        tk.Button(btn_frame, text="📷 Test Camera", bg="#475569", fg=FG, font=btn_font,
                  relief="flat", padx=10, pady=6, command=self._test_camera).pack(side="left", padx=(0, 6))

        tk.Button(btn_frame, text="📡 Test MQTT", bg="#475569", fg=FG, font=btn_font,
                  relief="flat", padx=10, pady=6, command=self._test_mqtt).pack(side="left")

        self._status_lbl = tk.Label(btn_frame, text="● Stopped", bg=BG, fg=RED, font=label_font)
        self._status_lbl.pack(side="left", padx=12)

        # Log
        tk.Label(self, text="Output:", bg=BG, fg=DIM, font=label_font, anchor="w").pack(fill="x", padx=16)
        self._log = scrolledtext.ScrolledText(self, bg="#020617", fg="#86efac",
                                              font=("monospace", 9), height=10,
                                              state="disabled", relief="flat")
        self._log.pack(fill="both", expand=True, padx=16, pady=(0, 12))

    def _toggle_advanced(self):
        if self._adv_visible.get():
            self._adv_container.pack_forget()
            self._adv_visible.set(False)
            self._adv_btn.configure(text="▶ Advanced")
        else:
            self._adv_container.pack(fill="x", after=self._adv_btn)
            for sec in self._adv_sections:
                sec.pack(in_=self._adv_container, fill="x", padx=16, pady=3)
            self._adv_visible.set(True)
            self._adv_btn.configure(text="▼ Advanced")

    def _browse(self, key):
        if key in ("ca_cert", "client_cert", "client_key"):
            filetypes = [("Cert/Key files", "*.crt *.key *.pem"), ("All files", "*.*")]
        else:
            filetypes = [("PyTorch model", "*.pt"), ("All files", "*.*")]
        path = filedialog.askopenfilename(title="Select file", filetypes=filetypes)
        if path:
            self._vars[key].set(path)

    def _save(self):
        v = {k: var.get() for k, var in self._vars.items()}
        save_config(v)
        self._log_line(f"✓ Config saved to {CONFIG_PATH}\n")

    def _start(self):
        self._save()
        self._start_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")
        self._status_lbl.configure(text="● Running", fg=GREEN)

        def _run():
            self._log_line(f"$ {PYTHON} -m edge.main\n")
            self._proc = subprocess.Popen(
                [PYTHON, "-m", "edge.main"],
                cwd=os.path.dirname(__file__),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
                env={**os.environ, "EDGE_CONFIG": CONFIG_PATH, "YOLO_AUTOINSTALL": "false"},
            )
            for line in self._proc.stdout:
                self._log_line(line)
            self._proc.wait()
            self.after(0, lambda: self._status_lbl.configure(text="● Stopped", fg=RED))
            self.after(0, lambda: self._start_btn.configure(state="normal"))
            self.after(0, lambda: self._stop_btn.configure(state="disabled"))

        threading.Thread(target=_run, daemon=True).start()

    def _stop(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
        self._stop_btn.configure(state="disabled")
        self._status_lbl.configure(text="● Stopped", fg=RED)
        self._start_btn.configure(state="normal")

    def _test_camera(self):
        url = self._vars["camera_source"].get().strip()
        self._log_line(f"Testing camera: {url}\n")

        def _run():
            # Run in venv python so cv2 and numpy are available
            script = f"""
import sys, urllib.request
url = {repr(url)}
try:
    import cv2, numpy as np
    if url.startswith("http"):
        req = urllib.request.urlopen(url, timeout=5)
        buf = b""
        for _ in range(50):
            buf += req.read(4096)
            s = buf.find(b"\\xff\\xd8")
            e = buf.find(b"\\xff\\xd9")
            if s != -1 and e != -1 and e > s:
                frame = cv2.imdecode(np.frombuffer(buf[s:e+2], dtype=np.uint8), cv2.IMREAD_COLOR)
                if frame is not None:
                    h, w = frame.shape[:2]
                    print(f"OK {{w}}x{{h}}")
                    sys.exit(0)
        print("NOFRAME")
    else:
        cap = cv2.VideoCapture(url)
        ret, frame = cap.read()
        cap.release()
        if ret and frame is not None:
            h, w = frame.shape[:2]
            print(f"OK {{w}}x{{h}}")
        else:
            print("NOFRAME")
except Exception as e:
    print(f"ERR {{e}}")
"""
            try:
                result = subprocess.run(
                    [PYTHON, "-c", script],
                    cwd=os.path.dirname(__file__),
                    capture_output=True, text=True, timeout=10,
                )
                out = (result.stdout + result.stderr).strip()
                if out.startswith("OK "):
                    dims = out[3:]
                    self._log_line(f"✓ Camera OK — frame {dims}\n")
                elif out.startswith("ERR "):
                    self._log_line(f"✗ Camera test failed: {out[4:]}\n")
                else:
                    self._log_line(f"⚠ Could not decode frame from camera\n")
            except subprocess.TimeoutExpired:
                self._log_line("✗ Camera test timed out\n")
            except Exception as e:
                self._log_line(f"✗ Camera test failed: {e}\n")

        threading.Thread(target=_run, daemon=True).start()

    def _test_mqtt(self):
        host = self._vars["mqtt_host"].get().strip()
        port = int(self._vars["mqtt_port"].get().strip())
        ca = self._vars["ca_cert"].get().strip()
        crt = self._vars["client_cert"].get().strip()
        key = self._vars["client_key"].get().strip()
        self._log_line(f"Testing MQTT connection to {host}:{port}…\n")

        def _run():
            script = f"""
import sys, time
try:
    import paho.mqtt.client as mqtt
    result = {{"ok": False}}
    c = mqtt.Client(client_id="launcher-test", clean_session=True)
    ca, crt, key = {repr(ca)}, {repr(crt)}, {repr(key)}
    if ca and crt and key:
        c.tls_set(ca_certs=ca, certfile=crt, keyfile=key)
    def on_connect(cl, u, f, rc):
        result["ok"] = (rc == 0)
        cl.disconnect()
    c.on_connect = on_connect
    c.connect({repr(host)}, {port}, keepalive=5)
    c.loop_start()
    time.sleep(3)
    c.loop_stop()
    print("OK" if result["ok"] else "FAIL")
except Exception as e:
    print(f"ERR {{e}}")
"""
            try:
                result = subprocess.run(
                    [PYTHON, "-c", script],
                    cwd=os.path.dirname(__file__),
                    capture_output=True, text=True, timeout=8,
                )
                out = (result.stdout + result.stderr).strip()
                if out.startswith("OK"):
                    self._log_line(f"✓ MQTT connected to {host}:{port}\n")
                elif out.startswith("ERR "):
                    self._log_line(f"✗ MQTT test failed: {out[4:]}\n")
                else:
                    self._log_line(f"✗ MQTT connection failed\n")
            except subprocess.TimeoutExpired:
                self._log_line("✗ MQTT test timed out\n")
            except Exception as e:
                self._log_line(f"✗ MQTT test error: {e}\n")

        threading.Thread(target=_run, daemon=True).start()

    def _log_line(self, text):
        self.after(0, lambda: self._log_append(text))

    def _log_append(self, text):
        self._log.configure(state="normal")
        self._log.insert(tk.END, text)
        self._log.see(tk.END)
        self._log.configure(state="disabled")


if __name__ == "__main__":
    app = EdgeLauncher()
    try:
        app.mainloop()
    except Exception as e:
        import traceback
        print("Launcher crashed:", traceback.format_exc())
