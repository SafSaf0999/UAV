#!/usr/bin/env python3
"""
UAV Control Center — Edge Device Launcher GUI
Run on the EDGE laptop (the one running inference).

Lets you configure the camera IP/port, MQTT host, model path, etc.,
writes edge/config.yaml, then starts/stops the edge process.
"""

import os
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, font as tkfont
from tkinter import scrolledtext

import yaml

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "edge", "config.yaml")
EXAMPLE_PATH = os.path.join(os.path.dirname(__file__), "edge", "config.example.yaml")

# UFW ports the edge device needs open (outbound is usually fine; open inbound for signaling)
UFW_PORTS = [
    ("8765", "tcp"),  # WebRTC signaling (if edge hosts it)
]

DEFAULTS = {
    "device_id":        "edge-01",
    "mqtt_host":        "10.42.0.1",   # typical hotspot gateway IP
    "mqtt_port":        "8883",
    "camera_source":    "http://192.168.43.1:8080/video",  # IP Webcam default
    "camera_fps":       "15",
    "model_path":       "",
    "active_model":     "daylight-v1",
    "lat":              "0.0",
    "lon":              "0.0",
    "ptz_enabled":      "false",
    "ptz_type":         "digital",
    "sensor_enabled":   "false",
    "sensor_url":       "http://192.168.43.1:8080/sensors.json",
    "estimator_enabled":"false",
    "signaling_url":    "ws://10.42.0.1:8090",
}


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def load_config() -> dict:
    path = CONFIG_PATH if os.path.exists(CONFIG_PATH) else EXAMPLE_PATH
    try:
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def build_config(v: dict) -> dict:
    """Build a config dict from the GUI field values."""
    cfg = {
        "device_id": v["device_id"],
        "mqtt": {
            "host": v["mqtt_host"],
            "port": int(v["mqtt_port"]),
        },
        "camera": {
            "source": v["camera_source"],
            "fps": int(v["camera_fps"]),
        },
        "location": {
            "lat": float(v["lat"]),
            "lon": float(v["lon"]),
        },
        "active_model": v["active_model"],
        "model_profiles": [],
        "signaling": {
            "url": v["signaling_url"],
        },
        "ptz": {
            "enabled": v["ptz_enabled"].lower() == "true",
            "hardware_type": v["ptz_type"],
        },
        "sensor": {
            "enabled": v["sensor_enabled"].lower() == "true",
            "source": "http",
            "http_url": v["sensor_url"],
            "poll_interval_s": 1.0,
        },
        "estimator": {
            "enabled": v["estimator_enabled"].lower() == "true",
            "fov_deg": 60.0,
            "reference_size_m": 0.5,
            "window_frames": 10,
        },
    }

    # Add model profile if a path was given
    if v["model_path"]:
        cfg["model_profiles"].append({
            "name": v["active_model"],
            "file_path": v["model_path"],
            "camera_mode": "daylight",
        })

    return cfg


def save_config(v: dict) -> None:
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    cfg = build_config(v)
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)


def run_cmd(cmd: list, cwd: str, log_widget: scrolledtext.ScrolledText,
            env: dict = None) -> int:
    def _append(text):
        log_widget.after(0, _append_safe, text)

    def _append_safe(text):
        log_widget.configure(state="normal")
        log_widget.insert(tk.END, text)
        log_widget.see(tk.END)
        log_widget.configure(state="disabled")

    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    try:
        proc = subprocess.Popen(
            cmd, cwd=cwd,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, env=merged_env,
        )
        for line in proc.stdout:
            _append(line)
        proc.wait()
        return proc.returncode
    except FileNotFoundError as e:
        _append(f"\nERROR: {e}\n")
        return 1


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class EdgeLauncher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Anti-UAV — Edge Device Launcher")
        self.resizable(True, True)
        self.configure(bg="#0f172a")
        self._proc = None
        self._build_ui()

    def _build_ui(self):
        BG   = "#0f172a"
        CARD = "#1e293b"
        ACC  = "#3b82f6"
        FG   = "#f1f5f9"
        DIM  = "#94a3b8"

        title_font = tkfont.Font(family="monospace", size=14, weight="bold")
        label_font = tkfont.Font(family="monospace", size=10)
        btn_font   = tkfont.Font(family="monospace", size=11, weight="bold")
        sec_font   = tkfont.Font(family="monospace", size=10, weight="bold")

        tk.Label(self, text="Anti-UAV Detection — Edge Device",
                 bg=BG, fg=FG, font=title_font).pack(pady=(16, 4))
        tk.Label(self, text="Configure camera, MQTT, and model, then start inference.",
                 bg=BG, fg=DIM, font=label_font).pack(pady=(0, 10))

        raw = load_config()
        self._vars = {}

        def _v(key):
            return tk.StringVar(value=DEFAULTS[key])

        for k in DEFAULTS:
            self._vars[k] = _v(k)

        # Pre-fill from existing config
        if raw:
            self._vars["device_id"].set(raw.get("device_id", DEFAULTS["device_id"]))
            self._vars["mqtt_host"].set(raw.get("mqtt", {}).get("host", DEFAULTS["mqtt_host"]))
            self._vars["mqtt_port"].set(str(raw.get("mqtt", {}).get("port", DEFAULTS["mqtt_port"])))
            self._vars["camera_source"].set(raw.get("camera", {}).get("source", DEFAULTS["camera_source"]))
            self._vars["camera_fps"].set(str(raw.get("camera", {}).get("fps", DEFAULTS["camera_fps"])))
            self._vars["active_model"].set(raw.get("active_model", DEFAULTS["active_model"]))
            self._vars["lat"].set(str(raw.get("location", {}).get("lat", DEFAULTS["lat"])))
            self._vars["lon"].set(str(raw.get("location", {}).get("lon", DEFAULTS["lon"])))
            self._vars["signaling_url"].set(raw.get("signaling", {}).get("url", DEFAULTS["signaling_url"]))
            profiles = raw.get("model_profiles", [])
            if profiles:
                self._vars["model_path"].set(profiles[0].get("file_path", ""))

        def section(parent, title):
            f = tk.Frame(parent, bg=CARD, padx=14, pady=10)
            f.pack(fill="x", padx=20, pady=4)
            tk.Label(f, text=title, bg=CARD, fg=ACC,
                     font=sec_font, anchor="w").grid(
                row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
            return f

        def row(parent, r, label, key, browse=False):
            tk.Label(parent, text=label + ":", bg=CARD, fg=DIM,
                     font=label_font, anchor="w", width=22).grid(
                row=r, column=0, sticky="w", pady=3)
            e = tk.Entry(parent, textvariable=self._vars[key],
                         bg="#0f172a", fg=FG, insertbackground=FG,
                         font=label_font, relief="flat", width=34)
            e.grid(row=r, column=1, sticky="ew", padx=(8, 0), pady=3)
            if browse:
                tk.Button(parent, text="…", bg="#334155", fg=FG,
                          font=label_font, relief="flat", padx=4,
                          command=lambda k=key: self._browse(k)).grid(
                    row=r, column=2, padx=(4, 0))
            parent.columnconfigure(1, weight=1)

        # ── Camera ──
        cam = section(self, "📷  Camera (IP Webcam)")
        row(cam, 1, "Camera URL", "camera_source")
        row(cam, 2, "FPS", "camera_fps")

        # ── MQTT ──
        mqtt = section(self, "📡  MQTT Broker (Main Device)")
        row(mqtt, 1, "Main Device IP", "mqtt_host")
        row(mqtt, 2, "MQTT Port", "mqtt_port")

        # ── Model ──
        mdl = section(self, "🤖  Model")
        row(mdl, 1, "Model .pt path", "model_path", browse=True)
        row(mdl, 2, "Active model name", "active_model")

        # ── Device ──
        dev = section(self, "🔧  Device")
        row(dev, 1, "Device ID", "device_id")
        row(dev, 2, "Latitude", "lat")
        row(dev, 3, "Longitude", "lon")
        row(dev, 4, "Signaling URL", "signaling_url")

        # ── Optional ──
        opt = section(self, "⚙  Optional")
        row(opt, 1, "PTZ Enabled", "ptz_enabled")
        row(opt, 2, "PTZ Type", "ptz_type")
        row(opt, 3, "Sensor Enabled", "sensor_enabled")
        row(opt, 4, "Sensor URL", "sensor_url")
        row(opt, 5, "Estimator Enabled", "estimator_enabled")

        # ── Buttons ──
        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack(fill="x", padx=20, pady=8)

        tk.Button(btn_frame, text="Open Firewall Ports",
                  bg="#475569", fg=FG, font=btn_font, relief="flat",
                  padx=12, pady=6,
                  command=self._open_ports).pack(side="left", padx=(0, 8))

        tk.Button(btn_frame, text="Save Config",
                  bg="#475569", fg=FG, font=btn_font, relief="flat",
                  padx=12, pady=6,
                  command=self._save).pack(side="left", padx=(0, 8))

        self._start_btn = tk.Button(
            btn_frame, text="▶  Start Inference",
            bg=ACC, fg="#fff", font=btn_font, relief="flat",
            padx=16, pady=8, command=self._start)
        self._start_btn.pack(side="left", padx=(0, 8))

        self._stop_btn = tk.Button(
            btn_frame, text="■  Stop",
            bg="#ef4444", fg="#fff", font=btn_font, relief="flat",
            padx=16, pady=8, command=self._stop, state="disabled")
        self._stop_btn.pack(side="left")

        self._status_lbl = tk.Label(btn_frame, text="● Stopped",
                                    bg=BG, fg="#ef4444", font=label_font)
        self._status_lbl.pack(side="left", padx=16)

        # ── Log ──
        tk.Label(self, text="Output:", bg=BG, fg=DIM,
                 font=label_font, anchor="w").pack(fill="x", padx=20)
        self._log = scrolledtext.ScrolledText(
            self, bg="#020617", fg="#86efac", font=("monospace", 9),
            height=14, state="disabled", relief="flat")
        self._log.pack(fill="both", expand=True, padx=20, pady=(0, 16))

    # ------------------------------------------------------------------

    def _browse(self, key):
        path = filedialog.askopenfilename(
            title="Select .pt model file",
            filetypes=[("PyTorch model", "*.pt"), ("All files", "*.*")],
        )
        if path:
            self._vars[key].set(path)

    def _save(self):
        v = {k: var.get() for k, var in self._vars.items()}
        save_config(v)
        self._log_line(f"✓ Config saved to {CONFIG_PATH}\n")

    def _open_ports(self):
        def _run():
            for port, proto in UFW_PORTS:
                cmd = ["sudo", "ufw", "allow", f"{port}/{proto}"]
                self._log_line(f"$ {' '.join(cmd)}\n")
                run_cmd(cmd, cwd=os.path.dirname(__file__), log_widget=self._log)
            run_cmd(["sudo", "ufw", "reload"],
                    cwd=os.path.dirname(__file__), log_widget=self._log)
            self._log_line("✓ Firewall rules applied\n")
        threading.Thread(target=_run, daemon=True).start()

    def _start(self):
        self._save()
        self._start_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")
        self._status_lbl.configure(text="● Running", fg="#22c55e")

        edge_dir = os.path.join(os.path.dirname(__file__), "edge")

        def _run():
            self._log_line("$ python main.py\n")
            self._proc = subprocess.Popen(
                ["python", "main.py"],
                cwd=edge_dir,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
                env={**os.environ, "EDGE_CONFIG": CONFIG_PATH},
            )
            for line in self._proc.stdout:
                self._log_line(line)
            self._proc.wait()
            self.after(0, lambda: self._status_lbl.configure(text="● Stopped", fg="#ef4444"))
            self.after(0, lambda: self._start_btn.configure(state="normal"))
            self.after(0, lambda: self._stop_btn.configure(state="disabled"))

        threading.Thread(target=_run, daemon=True).start()

    def _stop(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
        self._stop_btn.configure(state="disabled")
        self._status_lbl.configure(text="● Stopped", fg="#ef4444")
        self._start_btn.configure(state="normal")

    def _log_line(self, text):
        self.after(0, self._log_line_safe, text)

    def _log_line_safe(self, text):
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
