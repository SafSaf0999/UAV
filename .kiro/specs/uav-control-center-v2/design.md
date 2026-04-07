# Design Document: UAV Control Center v2

## Overview

This document describes the technical design for the v2 upgrade of the Anti-UAV Detection System control center. The existing system is fully operational — edge devices publish MQTT, the aggregation service consolidates state, and the React frontend provides basic UI. This upgrade layers new capabilities on top without breaking existing functionality.

The control center UI is a standalone Anti-UAV system — no third-party branding, no external service names appear anywhere in the frontend. The backend data bridge (which forwards UAV state to external automation systems) runs silently in Docker with zero UI presence.

---

## Architecture Changes

### New Services

```
Docker Compose Stack (additions)
├── ha_bridge          ← NEW: HA MQTT Discovery bridge
└── (existing services unchanged)

Edge Device (additions)
├── edge/health_reporter.py   ← NEW: publishes uav/health/{id}
└── edge/log_publisher.py     ← NEW: publishes uav/log/{id}
```

### New MQTT Topics

| Topic | Publisher | Subscriber | Description |
|---|---|---|---|
| `uav/health/{device_id}` | Edge Device | Aggregation, HA Bridge | CPU, memory, FPS, uptime |
| `uav/log/{device_id}` | Edge Device | Aggregation | WARNING+ log entries |
| `homeassistant/sensor/{device_id}/{entity}/config` | HA Bridge | Home Assistant | MQTT Discovery config |
| `homeassistant/sensor/{device_id}/{entity}/state` | HA Bridge | Home Assistant | Entity state updates |
| `homeassistant/binary_sensor/{device_id}/uav_detected/config` | HA Bridge | Home Assistant | Binary sensor discovery |
| `homeassistant/binary_sensor/{device_id}/uav_detected/state` | HA Bridge | Home Assistant | Binary sensor state |

---

## Component Designs

### 1. Auth Service (`main/control-center/auth.py`)

JWT-based authentication with invite-token registration and a full audit trail, layered onto the existing FastAPI control-center app.

**Endpoints:**

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/auth/login` | None | Returns JWT on valid credentials |
| `POST` | `/auth/register` | None | Creates account using invite token |
| `POST` | `/auth/logout` | JWT | Adds JTI to blocklist |
| `GET` | `/auth/me` | JWT | Returns `{username, display_name, role}` |
| `POST` | `/auth/invite` | Admin JWT | Generates one-time invite token |
| `GET` | `/auth/users` | Admin JWT | Lists all user accounts |
| `DELETE` | `/auth/users/{username}` | Admin JWT | Deactivates user, invalidates JWTs |
| `GET` | `/audit` | Admin JWT | Returns filtered audit log entries |

**User_Store (SQLite `auth.db`):**

```sql
CREATE TABLE users (
    username TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin', 'viewer')),
    created_at TEXT NOT NULL,
    last_login TEXT,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE invite_tokens (
    token TEXT PRIMARY KEY,
    role TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_by TEXT,
    used_at TEXT
);

CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    display_name TEXT NOT NULL,
    action TEXT NOT NULL,
    device_id TEXT,
    payload TEXT,
    timestamp TEXT NOT NULL
);
```

**Bootstrap:** On startup, if `users` table is empty, create an admin account from `BOOTSTRAP_ADMIN_USERNAME` + `BOOTSTRAP_ADMIN_PASSWORD` env vars.

**Invite token format:** `UAV-XXXX-XXXX` (uppercase alphanumeric, 8 random chars split by hyphen). Generated with `secrets.token_hex(4).upper()`.

**Registration flow:**
```
POST /auth/register {display_name, username, password, invite_token}
  1. Look up token in invite_tokens — 400 if not found
  2. Check expires_at > now — 400 if expired
  3. Check used_by IS NULL — 400 if already used
  4. Hash password with bcrypt
  5. INSERT into users
  6. UPDATE invite_tokens SET used_by, used_at
  7. Return JWT
```

**Audit middleware:** FastAPI middleware that intercepts `POST /api/command/*` and `POST /api/ptz/*`, extracts username from JWT, writes to `audit_log` table.

**JWT structure:**
```json
{
  "sub": "ahmed",
  "display_name": "Ahmed",
  "role": "viewer",
  "jti": "uuid4",
  "exp": 1234567890
}
```

**Deactivation:** Sets `users.active = 0`. JWT middleware checks `active` flag on every request — deactivated users get 401 immediately even with a valid token.

**Dependencies:** `python-jose[cryptography]`, `bcrypt`, `passlib`, `aiosqlite`

---

**Frontend — Registration page (`RegisterPage.tsx`):**

Separate from LoginPage. URL: `/register`. Shows:
- Invite token field (pre-filled if `?token=` query param present — admin can share a direct link)
- Display name field (e.g. "Ahmed Al-Rashid")
- Username field
- Password + confirm password fields
- "Create Account" button
- Link back to Login

**Frontend — Settings "Users" card (Admin only):**

```
┌─ Users ──────────────────────────────────────────┐
│  ahmed (Ahmed)    viewer   2026-04-04   [Deactivate] │
│  mubarak (Mubarak) admin  2026-04-01   [You]         │
│                                                      │
│  [+ Generate Invite Token]                           │
│  Role: [viewer ▼]  Expiry: [48h ▼]  [Generate]      │
│  Token: UAV-A3F9-K2M1  [Copy] [Share Link]           │
└──────────────────────────────────────────────────────┘
```

**Frontend — Settings "Audit Log" card (Admin only):**

```
┌─ Audit Log ──────────────────────────────────────────────────────┐
│  Filter: [All users ▼]  [All devices ▼]                          │
│  ──────────────────────────────────────────────────────────────  │
│  14:32:05  Ahmed      start_stream   edge-01                     │
│  14:33:12  Ahmed      zoom_in        edge-01                     │
│  14:45:00  Mubarak    switch_model   edge-02  → thermal-v1       │
│  15:01:33  Ahmed      stop_stream    edge-01                     │
└──────────────────────────────────────────────────────────────────┘
```

---

### 2. Health Reporter (`edge/health_reporter.py`)

Runs as a background thread started from `edge/main.py`.

```python
class HealthReporter:
    def __init__(self, config, mqtt_client, inference_engine):
        self._interval = 30  # seconds
        self._start_time = time.monotonic()
        self._mqtt_reconnects = 0  # incremented by MQTTClient
        self._camera_reconnects = 0  # incremented by CameraSource

    def _collect(self) -> dict:
        return {
            "device_id": self._device_id,
            "uptime_s": int(time.monotonic() - self._start_time),
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "inference_fps": self._engine.current_fps,
            "frames_processed": self._engine.frame_id,
            "mqtt_reconnects": self._mqtt_reconnects,
            "camera_reconnects": self._camera_reconnects,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
```

`InferenceEngine` gets a `current_fps` property computed as a rolling average over the last 30 frames.

---

### 3. Log Publisher (`edge/log_publisher.py`)

A Python `logging.Handler` subclass that publishes WARNING+ log records to MQTT.

```python
class MQTTLogHandler(logging.Handler):
    def emit(self, record):
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": self.format(record),
            "device_id": self._device_id,
        }
        self._mqtt_client.publish_log(json.dumps(entry).encode())
```

Added to the root logger at WARNING level in `edge/main.py`. Local file rotation handled by `logging.handlers.RotatingFileHandler` (50MB max, 7 backups).

---

### 4. Aggregation Service Extensions (`main/aggregation/`)

**`DeviceState` additions:**
```python
@dataclass
class DeviceState:
    # ... existing fields ...
    health: Optional[dict] = None          # latest Health_Payload
    class_counts: dict = field(default_factory=dict)  # {label: count}
    cert_info: Optional[dict] = None       # {cn, expires_at, issuer}
    log_entries: list = field(default_factory=list)   # last 500 entries
    detection_history: list = field(default_factory=list)  # last 50
```

**New registry methods:**
- `update_health(payload)` — stores health, notifies WS clients
- `update_log(entry)` — appends to log_entries (capped at 500), no WS push
- `_compute_class_counts(detections)` — called inside `update_tracking`

**New REST endpoints in `app.py`:**
- `GET /logs/{device_id}?limit=100&level=WARNING` — returns filtered log entries
- `GET /devices/{device_id}/health` — returns latest health payload

**`mqtt_subscriber.py` additions:**
- Subscribe to `uav/health/#` → `registry.update_health()`
- Subscribe to `uav/log/#` → `registry.update_log()`

---

### 5. Backend Data Bridge (`main/ha_bridge/bridge.py`)

Standalone Python script using `paho-mqtt`. Runs silently in Docker — no user-facing presence. Connects to Mosquitto on `mosquitto:1883` (internal Docker network).

**Discovery flow:**
```
On first message from device_id:
  1. Publish config to homeassistant/sensor/{device_id}/detection_count/config
  2. Publish config to homeassistant/binary_sensor/{device_id}/uav_detected/config
  3. Publish config for: active_model, device_status, cpu_percent, inference_fps,
     last_detection, compass_bearing, and one sensor per class label seen
  4. Mark device_id as "discovered"

On every subsequent message:
  1. Publish state to corresponding state_topic
```

**Discovery config example (detection_count):**
```json
{
  "unique_id": "uav_edge01_detection_count",
  "name": "edge-01 Detection Count",
  "state_topic": "homeassistant/sensor/edge-01/detection_count/state",
  "unit_of_measurement": "detections",
  "icon": "mdi:radar",
  "device": {
    "identifiers": ["uav_edge01"],
    "name": "UAV Edge Device edge-01",
    "model": "Anti-UAV Edge",
    "manufacturer": "UAV System"
  }
}
```

**State update example:**
```
Topic: homeassistant/sensor/edge-01/detection_count/state
Payload: 3
```

---

### 6. Frontend Architecture

#### Design Token Strategy

The UAV control center uses a design token system extracted from a reference open-source design system (the same token structure used by modern card-based dashboards). These are plain CSS custom properties — framework-agnostic — so they work identically in React. The token source files are at `/home/safsaf/Projects/UAV/frontend/src/resources/theme/` and are used as a reference only — no Lit/Web Component code is imported.

#### CSS Token File (`frontend/src/styles/design-tokens.css`)

```css
/* Design tokens for Anti-UAV Control Center */
/* Extracted from reference design system token files */

:root {
  /* ── Typography (from typography.globals.ts) ── */
  --ha-font-family-body: Roboto, Noto, sans-serif;
  --ha-font-family-code: monospace;
  --ha-font-size-xs: 10px;
  --ha-font-size-s: 12px;
  --ha-font-size-m: 14px;
  --ha-font-size-l: 16px;
  --ha-font-size-xl: 20px;
  --ha-font-size-2xl: 24px;
  --ha-font-size-3xl: 28px;
  --ha-font-weight-light: 300;
  --ha-font-weight-normal: 400;
  --ha-font-weight-medium: 500;
  --ha-font-weight-bold: 700;
  --ha-line-height-condensed: 1.2;
  --ha-line-height-normal: 1.6;
  --ha-line-height-expanded: 2;

  /* ── Spacing (from core.globals.ts) ── */
  --ha-space-1: 4px;
  --ha-space-2: 8px;
  --ha-space-3: 12px;
  --ha-space-4: 16px;
  --ha-space-5: 20px;
  --ha-space-6: 24px;
  --ha-space-8: 32px;
  --ha-space-10: 40px;
  --ha-space-12: 48px;
  --ha-space-14: 56px;

  /* ── Border radius (from core.globals.ts) ── */
  --ha-border-radius-sm: 4px;
  --ha-border-radius-md: 8px;
  --ha-border-radius-lg: 12px;
  --ha-border-radius-xl: 16px;
  --ha-border-radius-pill: 9999px;

  /* ── Neutral color scale (from color/core.globals.ts) ── */
  --ha-color-neutral-05: #141414;
  --ha-color-neutral-10: #202020;
  --ha-color-neutral-20: #363636;
  --ha-color-neutral-30: #4a4a4a;
  --ha-color-neutral-40: #5e5e5e;
  --ha-color-neutral-50: #7a7a7a;
  --ha-color-neutral-60: #989898;
  --ha-color-neutral-70: #b1b1b1;
  --ha-color-neutral-80: #cccccc;
  --ha-color-neutral-90: #e6e6e6;

  /* ── Primary (blue) scale (from color/core.globals.ts) ── */
  --ha-color-primary-05: #001721;
  --ha-color-primary-10: #002e3e;
  --ha-color-primary-20: #004156;
  --ha-color-primary-40: #009ac7;
  --ha-color-primary-50: #18bcf2;
  --ha-color-primary-60: #37c8fd;
  --ha-color-primary-70: #7bd4fb;

  /* ── Status colors (from color/core.globals.ts) ── */
  --ha-color-green-40: #1a7a3a;
  --ha-color-green-50: #2ea84f;
  --ha-color-green-60: #4dc96e;
  --ha-color-red-40: #b30532;
  --ha-color-red-50: #dc3146;
  --ha-color-red-60: #f3676c;
  --ha-color-orange-40: #9d3800;
  --ha-color-orange-50: #c94e00;
  --ha-color-orange-60: #f36d00;
  --ha-color-orange-70: #ff9342;

  /* ── Semantic aliases (from color/color.globals.ts) ── */
  --error-color: #db4437;
  --warning-color: #ffa600;
  --success-color: #43a047;
  --info-color: #039be5;

  /* ── Shadows (from semantic.globals.ts + core.globals.ts) ── */
  --ha-box-shadow-s: 0 2px 4px 0 rgba(0,0,0,0.4);
  --ha-box-shadow-m: 0 4px 8px 0 rgba(0,0,0,0.4);
  --ha-box-shadow-l: 0 8px 12px 0 rgba(0,0,0,0.4);
}

/* ── Dark theme (default for UAV — always dark) ── */
:root, [data-theme="dark"] {
  /* Backgrounds */
  --primary-background-color: #111111;
  --secondary-background-color: var(--ha-color-neutral-05);
  --card-background-color: var(--ha-color-neutral-10);
  --clear-background-color: var(--ha-color-neutral-05);

  /* Text (from color/semantic.globals.ts darkSemanticColorStyles) */
  --primary-text-color: #ffffff;
  --secondary-text-color: var(--ha-color-neutral-80);
  --disabled-text-color: var(--ha-color-neutral-50);

  /* Dividers */
  --divider-color: var(--ha-color-neutral-20);
  --outline-color: var(--ha-color-neutral-20);

  /* Card (from ha-card.ts) */
  --ha-card-background: var(--card-background-color);
  --ha-card-border-color: var(--ha-color-neutral-20);
  --ha-card-border-radius: var(--ha-border-radius-lg);
  --ha-card-box-shadow: var(--ha-box-shadow-m);

  /* Scrollbar */
  --scrollbar-thumb-color: var(--ha-color-neutral-30);

  /* Accent */
  --primary-color: var(--ha-color-primary-50);
  --accent-color: var(--ha-color-orange-60);
}

/* ── Light theme override ── */
[data-theme="light"] {
  --primary-background-color: #fafafa;
  --secondary-background-color: #e5e5e5;
  --card-background-color: #ffffff;
  --clear-background-color: #ffffff;
  --primary-text-color: #212121;
  --secondary-text-color: #727272;
  --disabled-text-color: #bdbdbd;
  --divider-color: rgba(0,0,0,0.12);
  --ha-card-border-color: rgba(0,0,0,0.12);
  --ha-box-shadow-s: 0 2px 4px 0 rgba(0,0,0,0.16);
  --ha-box-shadow-m: 0 4px 8px 0 rgba(0,0,0,0.16);
}
```

#### UAV-Specific Aliases (`frontend/src/styles/uav-tokens.css`)

```css
:root {
  /* Layout */
  --sidebar-width-expanded: 240px;
  --sidebar-width-collapsed: 64px;
  --topbar-height: var(--ha-space-14); /* 56px — matches HA header-height */
  --map-panel-width: 360px;

  /* UAV status colors — map to HA color scale */
  --uav-color-online: var(--ha-color-green-50);
  --uav-color-offline: var(--ha-color-neutral-50);
  --uav-color-alert: var(--ha-color-red-50);
  --uav-color-warning: var(--ha-color-orange-60);
  --uav-color-stream-active: var(--ha-color-primary-50);

  /* Detection class defaults */
  --uav-class-drone: var(--ha-color-red-50);
  --uav-class-bird: var(--ha-color-orange-60);
  --uav-class-person: var(--ha-color-primary-50);
  --uav-class-vehicle: #8b5cf6;
  --uav-class-default: var(--ha-color-neutral-60);
}
```

#### Component Tree (new)

```
App
├── AuthGuard (redirects to LoginPage if no valid JWT)
├── LoginPage
└── AppShell (authenticated)
    ├── Sidebar (collapsible, persisted in localStorage)
    ├── TopBar (connection status, user, logout)
    └── PageRouter
        ├── OverviewPage
        │   ├── StatSummaryRow (4 stat cards)
        │   └── DeviceGrid → DeviceCard[]
        ├── MapPage
        │   ├── MapContainer (Leaflet)
        │   └── MapPanel (slide-in, right side)
        │       ├── FeedCell (WebRTC, auto-start)
        │       ├── ClassBreakdown
        │       ├── HealthSnapshot
        │       ├── SensorDisplay (compass rose)
        │       └── PtzMiniControls
        ├── LiveFeedsPage (existing, fixed)
        ├── DevicesPage → DeviceCard[] (full list)
        ├── DeviceDetailPage
        │   ├── HealthGauges
        │   ├── CertInfo
        │   ├── ConnectionTimeline
        │   ├── ModelInfo
        │   └── DetectionHistory
        ├── PtzPage (existing)
        ├── SettingsPage
        │   ├── MqttConfigCard
        │   ├── CertPathsCard
        │   └── ModelProfilesCard
        └── LogsPage
            ├── LogFilters
            └── LogTable
```

#### CSS Design System

All components reference `ha-tokens.css` and `uav-tokens.css` variables. No hardcoded color values in component files.

```css
/* Example: Card component uses HA card tokens directly */
.card {
  background: var(--ha-card-background);
  border-radius: var(--ha-card-border-radius);   /* 12px from ha-card.ts */
  border: 1px solid var(--ha-card-border-color);
  box-shadow: var(--ha-card-box-shadow);
  padding: var(--ha-space-4);                    /* 16px from core.globals.ts */
  color: var(--primary-text-color);
  font-family: var(--ha-font-family-body);       /* Roboto, Noto, sans-serif */
  font-size: var(--ha-font-size-m);              /* 14px */
}

/* Example: StatChip uses HA color scale */
.stat-chip {
  border-radius: var(--ha-border-radius-pill);
  padding: var(--ha-space-1) var(--ha-space-2);
  font-size: var(--ha-font-size-s);
  font-weight: var(--ha-font-weight-medium);
}

/* Example: Status badge */
.badge-online  { color: var(--uav-color-online);  background: color-mix(in srgb, var(--uav-color-online) 15%, transparent); }
.badge-offline { color: var(--uav-color-offline); background: color-mix(in srgb, var(--uav-color-offline) 15%, transparent); }
.badge-alert   { color: var(--uav-color-alert);   background: color-mix(in srgb, var(--uav-color-alert) 15%, transparent); }
```

Theme toggle: `document.documentElement.setAttribute('data-theme', 'light'|'dark')` — persisted in `localStorage`.

#### Card Component

```tsx
// frontend/src/components/ui/Card.tsx
// Styled using extracted CSS design tokens
export function Card({ children, className, onClick }: CardProps) {
  return (
    <div className={`card ${className ?? ""}`} onClick={onClick}>
      {children}
    </div>
  );
}
// CSS uses: --ha-card-background, --ha-card-border-radius, --ha-card-border-color,
//           --ha-card-box-shadow, --ha-space-4, --primary-text-color
```

#### StatChip Component

```tsx
// frontend/src/components/ui/StatChip.tsx
// Uses --ha-border-radius-pill, --ha-space-1/2, --ha-font-size-s
export function StatChip({ label, count, color }: StatChipProps) {
  return (
    <span className="stat-chip" style={{
      color,
      background: `color-mix(in srgb, ${color} 15%, transparent)`
    }}>
      {label} ×{count}
    </span>
  );
}
```

#### DeviceCard Component

Shows: status dot, device ID, uptime, active model chip, per-class StatChips, last detection time, "View" + "Stream" buttons.

#### Tracking Overlay Fix

```tsx
// Fixed scale computation
const [videoDims, setVideoDims] = useState({ w: 640, h: 480 });

useEffect(() => {
  const video = videoRef.current;
  if (!video) return;
  const onMeta = () => setVideoDims({ w: video.videoWidth, h: video.videoHeight });
  video.addEventListener("loadedmetadata", onMeta);
  return () => video.removeEventListener("loadedmetadata", onMeta);
}, []);

// ResizeObserver on canvas
useEffect(() => {
  const canvas = canvasRef.current;
  if (!canvas) return;
  const ro = new ResizeObserver(() => {
    canvas.width = canvas.offsetWidth;
    canvas.height = canvas.offsetHeight;
  });
  ro.observe(canvas);
  return () => ro.disconnect();
}, []);

const scaleX = canvas.width / videoDims.w;
const scaleY = canvas.height / videoDims.h;
```

#### Auto-start Stream Logic

```tsx
// In LiveFeedsPage: send start_stream on mount for all online devices
useEffect(() => {
  for (const device of onlineDevices) {
    if (!activeStreams.has(device.device_id)) {
      sendCommand(device.device_id, { action: "start_stream" });
    }
  }
}, []);

// In DeviceCard thumbnail: Intersection Observer
useEffect(() => {
  const observer = new IntersectionObserver(([entry]) => {
    if (entry.isIntersecting && device.status === "online") {
      sendCommand(device.device_id, { action: "start_stream" });
    }
  });
  observer.observe(thumbRef.current);
  return () => observer.disconnect();
}, [device.device_id]);
```

#### Class Color System

```tsx
// frontend/src/utils/classColors.ts
const DEFAULT_COLORS: Record<string, string> = {
  drone: "#ef4444",
  bird: "#f59e0b",
  person: "#3b82f6",
  vehicle: "#8b5cf6",
};

export function getClassColor(label: string, profileColors?: Record<string, string>): string {
  return profileColors?.[label] ?? DEFAULT_COLORS[label] ?? "#94a3b8";
}
```

#### PWA Manifest

```json
{
  "name": "Anti-UAV Control Center",
  "short_name": "UAV Control",
  "display": "standalone",
  "background_color": "#0f172a",
  "theme_color": "#0f172a",
  "start_url": "/",
  "icons": [
    { "src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

---

## Launcher Redesigns

### Main Launcher

```
┌─────────────────────────────────────────────┐
│  Anti-UAV Control Center — Main Device      │
├─────────────────────────────────────────────┤
│  MQTT Port:          [8883      ]            │
│  Control Center:     [8080      ]            │
│  Remote Access:      [Local  ▼  ]            │
│  ▶ Advanced ────────────────────────────    │
├─────────────────────────────────────────────┤
│  Service Health                             │
│  ● mosquitto    ● aggregation               │
│  ● control-center  ● signaling              │
├─────────────────────────────────────────────┤
│  [▶ Start Stack] [■ Stop] [🌐 Open UI]      │
│  [🔑 Certs Tab]                             │
├─────────────────────────────────────────────┤
│  Certs Tab:                                 │
│  Server IP: [          ]                    │
│  Device IDs: [edge-01, edge-02]             │
│  [Generate Certs]                           │
│  ┌──────────┬──────────┬────────┬────────┐  │
│  │ File     │ CN       │ Expiry │ Action │  │
│  ├──────────┼──────────┼────────┼────────┤  │
│  │ ca.crt   │ AntiUAV  │ 2035   │ ✓      │  │
│  │ edge-01  │ edge-01  │ 2035   │ Copy→  │  │
│  └──────────┴──────────┴────────┴────────┘  │
└─────────────────────────────────────────────┘
```

### Edge Launcher

```
┌─────────────────────────────────────────────┐
│  Anti-UAV Detection — Edge Device           │
├─────────────────────────────────────────────┤
│  Camera URL:    [http://...          ] [📷] │
│  Main Device IP:[10.86.85.6          ]      │
│  Model .pt:     [/path/to/model.pt   ] [📂] │
│  ▶ Advanced ────────────────────────────    │
├─────────────────────────────────────────────┤
│  [▶ Start] [■ Stop] [Test Camera] [Test MQTT]│
└─────────────────────────────────────────────┘
```

---

## Data Flow Additions

### Health Data Flow

```
Edge Device (psutil) → uav/health/{id} → Aggregation → DeviceState.health
                                       → HA Bridge → homeassistant/sensor/.../state
                                       → WebSocket → Frontend DeviceCard health gauges
```

### Log Data Flow

```
Edge Device (logging.Handler) → uav/log/{id} → Aggregation → DeviceState.log_entries
                                              → REST GET /logs/{id} → Frontend LogsPage
```

### Auth Flow

```
── First-time setup ──────────────────────────────────────────────
Bootstrap admin account from BOOTSTRAP_ADMIN_USERNAME env var
  (only runs if users table is empty)

── Invite flow ───────────────────────────────────────────────────
Admin → POST /auth/invite {role: "viewer", expiry: "48h"}
      ← {token: "UAV-A3F9-K2M1", expires_at: "..."}
Admin → sends token out-of-band (WhatsApp, email, etc.)

── Registration flow ─────────────────────────────────────────────
New user → POST /auth/register {display_name, username, password, invite_token}
         ← validates token → creates account → returns JWT
         (token marked as used, cannot be reused)

── Login flow ────────────────────────────────────────────────────
User → POST /auth/login {username, password}
     ← {access_token: JWT}
User → GET /api/* (Authorization: Bearer JWT)
     → JWTMiddleware validates signature, expiry, active flag
     → proxies to aggregation

── Audit trail ───────────────────────────────────────────────────
User → POST /api/command/edge-01 {action: "start_stream"}
     → AuditMiddleware writes: {username, display_name, action, device_id, timestamp}
     → proxies to aggregation

── Deactivation ──────────────────────────────────────────────────
Admin → DELETE /auth/users/ahmed
      → sets users.active = 0
      → Ahmed's next request returns 401 immediately
```

---

## Error Handling Additions

| Condition | Behavior |
|---|---|
| JWT expired or invalid | Return 401; frontend redirects to LoginPage |
| Login with wrong credentials | Return 401 with generic "Invalid credentials" message (no hint whether username or password was wrong) |
| Invite token expired | Return 400 "Invite token has expired" |
| Invite token already used | Return 400 "Invite token has already been used" |
| Invite token not found | Return 400 "Invalid invite token" (same message as not found — no enumeration) |
| Deactivated user makes request | Return 401; frontend redirects to LoginPage |
| Health payload `cpu_percent` out of range | Log warning, clamp to [0, 100], store clamped value |
| Log entry missing required field | Discard silently, log warning in aggregation |
| HA Bridge MQTT disconnect | Reconnect with exponential backoff, re-publish discovery on reconnect |
| Stream shows black (no video data) | Show "Waiting for stream…" spinner; timeout after 10s shows "Stream failed" |
| Cert expiry within 30 days | Show amber warning badge on DeviceCard and in Device Detail cert section |

---

## Testing Strategy

### Property-Based Tests

| Property | Test | Library |
|---|---|---|
| P1: JWT round-trip | Issue JWT, verify it, check expiry | `hypothesis` + `python-jose` |
| P2: Health payload ranges | Generate random health dicts, assert field ranges | `hypothesis` |
| P3: Class counts sum | Generate random detection arrays, assert sum(class_counts) == len(detections) | `hypothesis` |
| P4: Log entry fields | Generate random log entries, assert all 5 required fields present | `hypothesis` |
| P5: HA discovery fields | Generate random device IDs, assert discovery config has required fields | `hypothesis` |

### Unit Tests

- Auth: login success, login failure, token expiry, viewer role blocks PTZ
- Health reporter: payload structure, field ranges
- Log publisher: WARNING emitted, DEBUG not emitted
- Aggregation: class_counts computed correctly, log_entries capped at 500
- HA bridge: discovery config structure, state update format
- Tracking overlay: scale factors use video dimensions, not hardcoded values
