#!/usr/bin/env python3
"""
Anti-UAV Detection — Edge Device Launcher
Three-tab UI: Config, Status, Logs.
"""

import os
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, font as tkfont, ttk

import yaml

VENV_PYTHON = os.path.join(os.path.dirname(__file__), ".venv", "bin", "python3")
PYTHON = VENV_PYTHON if os.path.exists(VENV_PYTHON) else "python3"

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "edge", "config.yaml")
EXAMPLE_PATH = os.path.join(os.path.dirname(__file__), "edge", "config.example.yaml")

BG = "#0f172a"
CARD = "#1e293b"
ACC = "#3b82f6"
FG = "#f1f5f9"
DIM = "#94a3b8"
GREEN = "#22c55e"
RED = "#ef4444"
AMBER = "#f59e0b"

DEFAULTS = {
    "device_id": "edge-01",
    "mqtt_host": "10.42.0.1",
    "mqtt_port": "8883",
    "mqtt_username": "edge-01",
    "mqtt_password": "",
    "camera_source": "http://10.202.184.184:8080/video",
    "camera_fps": "15",
    "model_path": "",
    "active_model": "daylight-v1",
    "lat": "0.0",
    "lon": "0.0",
    "signaling_url": "ws://10.42.0.1:8090",
    "ipwebcam_url": "",
}

# Shared state updated by inference thread
_mqtt_connected = False
_camera_reconnect_count = 0


def load_config():
    path = CONFIG_PATH if os.path.exists(CONFIG_PATH) else EXAMPLE_PATH
    try:
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def build_config(v):
    cfg = {
        "device_id": v["device_id"],
        "mqtt": {
            "host": v["mqtt_host"],
            "port": int(v["mqtt_port"]),
        },
        "camera": {"source": v["camera_source"], "fps": int(v["camera_fps"])},
        "location": {"lat": float(v["lat"]), "lon": float(v["lon"])},
        "active_model": v["active_model"],
        "model_profiles": (
            [{"name": v["active_model"], "file_path": v["model_path"], "camera_mode": "daylight"}]
            if v["model_path"] else []
        ),
        "signaling": {"url": v["signaling_url"]},
        "ptz": {"enabled": False, "hardware_type": "digital"},
        "sensor": {"enabled": False, "source": "http",
                   "http_url": "", "poll_interval_s": 1.0},
        "estimator": {"enabled": False, "fov_deg": 60.0,
                      "reference_size_m": 0.5, "window_frames": 10},
    }
    if v.get("mqtt_username"):
        cfg["mqtt"]["username"] = v["mqtt_username"]
    if v.get("mqtt_password"):
        cfg["mqtt"]["password"] = v["mqtt_password"]
    if v.get("ipwebcam_url"):
        cfg["ipwebcam"] = {"url": v["ipwebcam_url"]}
    return cfg


def save_config(v):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(build_config(v), f, default_flow_style=False, sort_keys=False)


class EdgeLauncher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Anti-UAV — Edge Device Launcher")
        self.configure(bg=BG)
        self.geometry("720x640")
        self.resizable(True, True)
        self._proc = None
        self._log_thread = None
        self._status_job = None
        self._apply_style()
        self._build_ui()
        self._schedule_status_poll()

    def _apply_style(self):
        style = ttk.Style(self)
        style.theme_use("default")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=CARD, foreground=DIM,
                        padding=[12, 6], font=("monospace", 10))
        style.map("TNotebook.Tab",
                  background=[("selected", ACC)],
                  foreground=[("selected", "#ffffff")])
        style.configure("TFrame", background=BG)

    def _build_ui(self):
        title_font = tkfont.Font(family="monospace", size=13, weight="bold")
        tk.Label(self, text="Anti-UAV Detection — Edge Device",
                 bg=BG, fg=FG, font=title_font).pack(pady=(14, 6))

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        config_frame = tk.Frame(nb, bg=BG)
        status_frame = tk.Frame(nb, bg=BG)
        logs_frame = tk.Frame(nb, bg=BG)

        nb.add(config_frame, text="  Config  ")
        nb.add(status_frame, text="  Status  ")
        nb.add(logs_frame, text="  Logs  ")

        self._build_config_tab(config_frame)
        self._build_status_tab(status_frame)
        self._build_logs_tab(logs_frame)

    # ── Config tab ─────────────────────────────────────────────────────────

    def _build_config_tab(self, parent):
        label_font = tkfont.Font(family="monospace", size=10)
        btn_font = tkfont.Font(family="monospace", size=10, weight="bold")
        sec_font = tkfont.Font(family="monospace", size=10, weight="bold")

        canvas = tk.Canvas(parent, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=BG)
        scroll_frame.bind("<Configure>",
                          lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        raw = load_config()
        self._vars = {k: tk.StringVar(value=v) for k, v in DEFAULTS.items()}

        # Pre-fill from existing config
        if raw:
            self._vars["device_id"].set(raw.get("device_id", DEFAULTS["device_id"]))
            mqtt = raw.get("mqtt", {})
            self._vars["mqtt_host"].set(mqtt.get("host", DEFAULTS["mqtt_host"]))
            self._vars["mqtt_port"].set(str(mqtt.get("port", DEFAULTS["mqtt_port"])))
            self._vars["mqtt_username"].set(mqtt.get("username", DEFAULTS["mqtt_username"]))
            self._vars["mqtt_password"].set(mqtt.get("password", DEFAULTS["mqtt_password"]))
            cam = raw.get("camera", {})
            self._vars["camera_source"].set(cam.get("source", DEFAULTS["camera_source"]))
            self._vars["camera_fps"].set(str(cam.get("fps", DEFAULTS["camera_fps"])))
            self._vars["active_model"].set(raw.get("active_model", DEFAULTS["active_model"]))
            loc = raw.get("location", {})
            self._vars["lat"].set(str(loc.get("lat", DEFAULTS["lat"])))
            self._vars["lon"].set(str(loc.get("lon", DEFAULTS["lon"])))
            self._vars["signaling_url"].set(
                raw.get("signaling", {}).get("url", DEFAULTS["signaling_url"]))
            profiles = raw.get("model_profiles", [])
            if profiles:
                self._vars["model_path"].set(profiles[0].get("file_path", ""))
            ipwebcam = raw.get("ipwebcam", {})
            self._vars["ipwebcam_url"].set(ipwebcam.get("url", ""))

        def section(title):
            f = tk.Frame(scroll_frame, bg=CARD, padx=14, pady=8)
            f.pack(fill="x", padx=8, pady=3)
            tk.Label(f, text=title, bg=CARD, fg=ACC, font=sec_font, anchor="w").grid(
                row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))
            return f

        def field_row(parent, r, label, key, show="", browse=False):
            tk.Label(parent, text=label + ":", bg=CARD, fg=DIM, font=label_font,
                     anchor="w", width=22).grid(row=r, column=0, sticky="w", pady=2)
            e = tk.Entry(parent, textvariable=self._vars[key], bg=BG, fg=FG,
                         insertbackground=FG, font=label_font, relief="flat", width=30,
                         show=show)
            e.grid(row=r, column=1, sticky="ew", padx=(8, 0), pady=2)
            if browse:
                tk.Button(parent, text="…", bg="#334155", fg=FG, font=label_font,
                          relief="flat", padx=4,
                          command=lambda k=key: self._browse(k)).grid(
                    row=r, column=2, padx=(4, 0))
            parent.columnconfigure(1, weight=1)

        # Primary
        prim = section("Camera")
        field_row(prim, 1, "Camera URL", "camera_source")
        field_row(prim, 2, "IP Webcam URL (opt)", "ipwebcam_url")

        # Camera preview
        self._cam_preview_lbl = tk.Label(prim, bg=CARD, text="[no preview]",
                                         fg=DIM, font=label_font)
        self._cam_preview_lbl.grid(row=3, column=0, columnspan=3, pady=(4, 2))
        tk.Button(prim, text="📷 Preview Frame", bg="#334155", fg=FG, font=label_font,
                  relief="flat", padx=6, pady=3,
                  command=self._preview_camera).grid(row=4, column=0, columnspan=3,
                                                     sticky="w", pady=(2, 4))

        # MQTT
        mqtt_sec = section("MQTT")
        field_row(mqtt_sec, 1, "Main Device IP", "mqtt_host")
        field_row(mqtt_sec, 2, "MQTT Port", "mqtt_port")
        field_row(mqtt_sec, 3, "Username", "mqtt_username")
        field_row(mqtt_sec, 4, "Password", "mqtt_password", show="*")

        # Test connection button + status label
        self._conn_status_lbl = tk.Label(mqtt_sec, text="", bg=CARD, fg=DIM, font=label_font)
        self._conn_status_lbl.grid(row=5, column=1, sticky="w", padx=(8, 0), pady=2)
        tk.Button(mqtt_sec, text="Test Connection", bg="#334155", fg=FG, font=label_font,
                  relief="flat", padx=6, pady=3,
                  command=self._test_connection).grid(row=5, column=0, sticky="w", pady=(4, 2))

        # Model
        model_sec = section("Model")
        field_row(model_sec, 1, "Model .pt path", "model_path", browse=True)
        field_row(model_sec, 2, "Active Model Name", "active_model")

        # Device
        dev_sec = section("Device")
        field_row(dev_sec, 1, "Device ID", "device_id")
        field_row(dev_sec, 2, "FPS", "camera_fps")
        field_row(dev_sec, 3, "Latitude", "lat")
        field_row(dev_sec, 4, "Longitude", "lon")
        field_row(dev_sec, 5, "Signaling URL", "signaling_url")

        # Buttons
        btn_frame = tk.Frame(scroll_frame, bg=BG)
        btn_frame.pack(fill="x", padx=8, pady=8)

        tk.Button(btn_frame, text="Save Config", bg="#475569", fg=FG, font=btn_font,
                  relief="flat", padx=10, pady=6, command=self._save).pack(side="left", padx=(0, 6))

        self._start_btn = tk.Button(btn_frame, text="▶ Start Inference", bg=ACC, fg="#fff",
                                    font=btn_font, relief="flat", padx=12, pady=6,
                                    command=self._start)
        self._start_btn.pack(side="left", padx=(0, 6))

        self._stop_btn = tk.Button(btn_frame, text="■ Stop", bg=RED, fg="#fff",
                                   font=btn_font, relief="flat", padx=12, pady=6,
                                   command=self._stop, state="disabled")
        self._stop_btn.pack(side="left")

    # ── Status tab ─────────────────────────────────────────────────────────

    def _build_status_tab(self, parent):
        label_font = tkfont.Font(family="monospace", size=10)
        sec_font = tkfont.Font(family="monospace", size=10, weight="bold")
        dot_font = tkfont.Font(family="monospace", size=14)

        header = tk.Frame(parent, bg=CARD, padx=14, pady=10)
        header.pack(fill="x", padx=16, pady=(12, 4))
        tk.Label(header, text="Edge Device Status", bg=CARD, fg=ACC, font=sec_font).pack(anchor="w")

        rows = tk.Frame(parent, bg=CARD, padx=14, pady=10)
        rows.pack(fill="x", padx=16, pady=4)

        # Inference process row
        self._inf_dot = tk.Label(rows, text="●", bg=CARD, fg=RED, font=dot_font)
        self._inf_dot.grid(row=0, column=0, padx=(0, 8), pady=6, sticky="w")
        tk.Label(rows, text="Inference Process", bg=CARD, fg=FG, font=label_font,
                 width=22, anchor="w").grid(row=0, column=1, sticky="w", pady=6)
        self._inf_state_lbl = tk.Label(rows, text="Stopped", bg=CARD, fg=RED, font=label_font)
        self._inf_state_lbl.grid(row=0, column=2, sticky="w", padx=(8, 0), pady=6)

        # MQTT connection row
        self._mqtt_dot = tk.Label(rows, text="●", bg=CARD, fg=RED, font=dot_font)
        self._mqtt_dot.grid(row=1, column=0, padx=(0, 8), pady=6, sticky="w")
        tk.Label(rows, text="MQTT Connection", bg=CARD, fg=FG, font=label_font,
                 width=22, anchor="w").grid(row=1, column=1, sticky="w", pady=6)
        self._mqtt_state_lbl = tk.Label(rows, text="Disconnected", bg=CARD, fg=RED, font=label_font)
        self._mqtt_state_lbl.grid(row=1, column=2, sticky="w", padx=(8, 0), pady=6)

        # Camera reconnect count row
        self._cam_dot = tk.Label(rows, text="●", bg=CARD, fg=DIM, font=dot_font)
        self._cam_dot.grid(row=2, column=0, padx=(0, 8), pady=6, sticky="w")
        tk.Label(rows, text="Camera Reconnects", bg=CARD, fg=FG, font=label_font,
                 width=22, anchor="w").grid(row=2, column=1, sticky="w", pady=6)
        self._cam_count_lbl = tk.Label(rows, text="0", bg=CARD, fg=DIM, font=label_font)
        self._cam_count_lbl.grid(row=2, column=2, sticky="w", padx=(8, 0), pady=6)

        rows.columnconfigure(2, weight=1)

    # ── Logs tab ───────────────────────────────────────────────────────────

    def _build_logs_tab(self, parent):
        label_font = tkfont.Font(family="monospace", size=10)
        btn_font = tkfont.Font(family="monospace", size=10, weight="bold")

        ctrl = tk.Frame(parent, bg=BG)
        ctrl.pack(fill="x", padx=16, pady=(8, 4))
        tk.Label(ctrl, text="Inference output", bg=BG, fg=DIM, font=label_font).pack(side="left")
        tk.Button(ctrl, text="Clear", bg="#475569", fg=FG, font=btn_font,
                  relief="flat", padx=8, pady=3, command=self._clear_logs).pack(side="right")

        self._log = tk.Text(parent, bg="#020617", fg="#86efac",
                            font=("monospace", 9), state="disabled",
                            relief="flat", wrap="none")
        vsb = ttk.Scrollbar(parent, orient="vertical", command=self._log.yview)
        hsb = ttk.Scrollbar(parent, orient="horizontal", command=self._log.xview)
        self._log.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        hsb.pack(side="bottom", fill="x", padx=16)
        vsb.pack(side="right", fill="y")
        self._log.pack(fill="both", expand=True, padx=(16, 0), pady=(0, 8))

    def _clear_logs(self):
        self._log.configure(state="normal")
        self._log.delete("1.0", tk.END)
        self._log.configure(state="disabled")

    def _log_append(self, text):
        self._log.configure(state="normal")
        self._log.insert(tk.END, text)
        self._log.see(tk.END)
        self._log.configure(state="disabled")

    # ── Camera preview ─────────────────────────────────────────────────────

    def _preview_camera(self):
        url = self._vars["camera_source"].get().strip()
        self._cam_preview_lbl.configure(text="[fetching…]", image="")

        def _run():
            try:
                import urllib.request
                import io
                try:
                    import cv2
                    import numpy as np
                    _has_cv2 = True
                except ImportError:
                    _has_cv2 = False

                try:
                    from PIL import Image, ImageTk
                    _has_pil = True
                except ImportError:
                    _has_pil = False

                if not _has_cv2 and not _has_pil:
                    self.after(0, lambda: self._cam_preview_lbl.configure(
                        text="[preview unavailable: install opencv-python or Pillow]"))
                    return

                frame_bytes = None
                if url.startswith("http"):
                    req = urllib.request.urlopen(url, timeout=5)
                    buf = b""
                    for _ in range(100):
                        buf += req.read(4096)
                        s = buf.find(b"\xff\xd8")
                        e = buf.find(b"\xff\xd9")
                        if s != -1 and e != -1 and e > s:
                            frame_bytes = buf[s:e + 2]
                            break

                if frame_bytes is None and not url.startswith("http"):
                    # Try as file path
                    with open(url, "rb") as fh:
                        frame_bytes = fh.read()

                if frame_bytes is None:
                    self.after(0, lambda: self._cam_preview_lbl.configure(
                        text="[could not decode frame]"))
                    return

                if _has_pil:
                    img = Image.open(io.BytesIO(frame_bytes))
                    img.thumbnail((120, 90))
                    photo = ImageTk.PhotoImage(img)
                    self.after(0, lambda p=photo: self._set_preview(p))
                elif _has_cv2:
                    arr = np.frombuffer(frame_bytes, dtype=np.uint8)
                    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    if frame is None:
                        self.after(0, lambda: self._cam_preview_lbl.configure(
                            text="[decode failed]"))
                        return
                    frame = cv2.resize(frame, (120, 90))
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    from PIL import Image, ImageTk
                    img = Image.fromarray(frame_rgb)
                    photo = ImageTk.PhotoImage(img)
                    self.after(0, lambda p=photo: self._set_preview(p))

            except Exception as ex:
                self.after(0, lambda: self._cam_preview_lbl.configure(
                    text=f"[preview error: {ex}]", image=""))

        threading.Thread(target=_run, daemon=True).start()

    def _set_preview(self, photo):
        self._cam_preview_lbl.configure(image=photo, text="")
        self._cam_preview_lbl._photo = photo  # keep reference

    # ── Test MQTT connection ────────────────────────────────────────────────

    def _test_connection(self):
        host = self._vars["mqtt_host"].get().strip()
        port = self._vars["mqtt_port"].get().strip()
        username = self._vars["mqtt_username"].get().strip()
        password = self._vars["mqtt_password"].get().strip()
        self._conn_status_lbl.configure(text="Testing…", fg=AMBER)

        def _run():
            script = f"""
import sys, time
try:
    import paho.mqtt.client as mqtt
    result = {{"ok": False}}
    c = mqtt.Client(client_id="launcher-test", clean_session=True)
    if {repr(username)}:
        c.username_pw_set({repr(username)}, {repr(password)})
    def on_connect(cl, u, f, rc):
        result["ok"] = (rc == 0)
        cl.disconnect()
    c.on_connect = on_connect
    c.connect({repr(host)}, {repr(int(port))}, keepalive=5)
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
                    self.after(0, lambda: self._conn_status_lbl.configure(
                        text=f"✓ Connected to {host}:{port}", fg=GREEN))
                elif out.startswith("ERR "):
                    self.after(0, lambda: self._conn_status_lbl.configure(
                        text=f"✗ {out[4:]}", fg=RED))
                else:
                    self.after(0, lambda: self._conn_status_lbl.configure(
                        text="✗ Connection failed", fg=RED))
            except subprocess.TimeoutExpired:
                self.after(0, lambda: self._conn_status_lbl.configure(
                    text="✗ Timed out", fg=RED))
            except Exception as e:
                self.after(0, lambda: self._conn_status_lbl.configure(
                    text=f"✗ {e}", fg=RED))

        threading.Thread(target=_run, daemon=True).start()

    # ── Browse ─────────────────────────────────────────────────────────────

    def _browse(self, key):
        filetypes = [("PyTorch model", "*.pt"), ("All files", "*.*")]
        path = filedialog.askopenfilename(title="Select file", filetypes=filetypes)
        if path:
            self._vars[key].set(path)

    # ── Inference process ──────────────────────────────────────────────────

    def _save(self):
        v = {k: var.get() for k, var in self._vars.items()}
        save_config(v)
        self._log_append(f"✓ Config saved to {CONFIG_PATH}\n")

    def _start(self):
        self._save()
        self._start_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")

        def _run():
            self.after(0, lambda: self._log_append(f"$ {PYTHON} -m edge.main\n"))
            self._proc = subprocess.Popen(
                [PYTHON, "-m", "edge.main"],
                cwd=os.path.dirname(__file__),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
                env={**os.environ, "EDGE_CONFIG": CONFIG_PATH, "YOLO_AUTOINSTALL": "false"},
            )
            for line in self._proc.stdout:
                self.after(0, lambda l=line: self._log_append(l))
                # Detect MQTT connected/disconnected from log output
                ll = line.lower()
                if "mqtt" in ll and ("connected" in ll or "connect" in ll):
                    global _mqtt_connected
                    _mqtt_connected = True
                elif "mqtt" in ll and ("disconnect" in ll or "error" in ll):
                    _mqtt_connected = False
                # Detect camera reconnect
                if "reconnect" in ll or "camera reconnect" in ll:
                    global _camera_reconnect_count
                    _camera_reconnect_count += 1

            self._proc.wait()
            self.after(0, self._on_proc_stopped)

        self._log_thread = threading.Thread(target=_run, daemon=True)
        self._log_thread.start()

    def _stop(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
        self._stop_btn.configure(state="disabled")
        self._start_btn.configure(state="normal")

    def _on_proc_stopped(self):
        self._start_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")
        global _mqtt_connected
        _mqtt_connected = False

    # ── Status polling ─────────────────────────────────────────────────────

    def _schedule_status_poll(self):
        self._update_status_tab()
        self._status_job = self.after(2000, self._schedule_status_poll)

    def _update_status_tab(self):
        # Inference process
        running = self._proc is not None and self._proc.poll() is None
        if running:
            self._inf_dot.configure(fg=GREEN)
            self._inf_state_lbl.configure(text="Running", fg=GREEN)
        else:
            self._inf_dot.configure(fg=RED)
            self._inf_state_lbl.configure(text="Stopped", fg=RED)

        # MQTT state
        if _mqtt_connected:
            self._mqtt_dot.configure(fg=GREEN)
            self._mqtt_state_lbl.configure(text="Connected", fg=GREEN)
        else:
            self._mqtt_dot.configure(fg=RED)
            self._mqtt_state_lbl.configure(text="Disconnected", fg=RED)

        # Camera reconnect count
        count = _camera_reconnect_count
        color = RED if count > 0 else DIM
        self._cam_dot.configure(fg=color)
        self._cam_count_lbl.configure(text=str(count), fg=color)


if __name__ == "__main__":
    app = EdgeLauncher()
    try:
        app.mainloop()
    except Exception as e:
        import traceback
        print("Launcher crashed:", traceback.format_exc())
