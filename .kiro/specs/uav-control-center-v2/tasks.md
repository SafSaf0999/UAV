# Implementation Plan: UAV Control Center v2

## Overview

All tasks build on the existing working system. No existing functionality is removed. Tasks are ordered so each layer is testable before the next begins. Backend tasks come before frontend tasks that depend on them.

## Tasks

- [x] 1. Auth service — backend
  - Add `python-jose[cryptography]`, `bcrypt`, `passlib`, `aiosqlite` to `main/control-center/requirements.txt`
  - Write `main/control-center/auth.py`:
    - SQLite User_Store (`auth.db`) with `users`, `invite_tokens`, `audit_log` tables via `aiosqlite`
    - Bootstrap admin on first startup from `BOOTSTRAP_ADMIN_USERNAME` + `BOOTSTRAP_ADMIN_PASSWORD` env vars
    - `POST /auth/login` — bcrypt verify, return JWT
    - `POST /auth/register` — validate invite token (exists, not expired, not used), create user, mark token consumed, return JWT
    - `POST /auth/invite` (Admin) — generate `UAV-XXXX-XXXX` token, store in DB with role + expiry
    - `POST /auth/logout` — add JTI to in-memory blocklist
    - `GET /auth/me` — return username, display_name, role
    - `GET /auth/users` (Admin) — list all users with created_at, last_login
    - `DELETE /auth/users/{username}` (Admin) — set active=0
    - `GET /audit` (Admin) — return filtered audit_log entries
  - Write `JWTMiddleware`: validates Bearer token on all `/api/*` routes and `?token=` on `/ws`; checks `active` flag; returns 401 on failure; exempts `/auth/*` and static routes
  - Write `AuditMiddleware`: intercepts `POST /api/command/*` and `POST /api/ptz/*`, writes audit_log entry with username, display_name, action, device_id, payload, timestamp
  - Wire both middleware into `main/control-center/app.py`
  - Add `BOOTSTRAP_ADMIN_USERNAME`, `BOOTSTRAP_ADMIN_PASSWORD`, `JWT_SECRET`, `JWT_TTL_HOURS` to `docker/.env.example`
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.10, 1.11, 1.12, 1.13, 1.14, 1.16, 1.17, 1.20_

- [x] 2. Auth service — tests
  - Write `main/control-center/tests/test_auth.py`:
    - Login success returns JWT with correct claims
    - Login failure returns 401
    - Expired token rejected by middleware
    - Valid token accepted
    - Viewer role stored in JWT claims, blocks PTZ endpoint
    - Register with valid invite token creates account and returns JWT
    - Register with expired token returns 400
    - Register with already-used token returns 400
    - Deactivated user gets 401 on next request
    - Audit log entry written on command POST
  - Write property test for JWT round-trip (Property 1): generate random username/role pairs, issue JWT, verify, assert claims match
  - Write property test for invite token single-use guarantee (Property 6): consume a token once, assert second use returns 400
  - _Requirements: 1.1, 1.3, 1.5, 1.11, 1.12_

- [x] 3. Frontend — login and register pages
  - Write `frontend/src/pages/LoginPage.tsx`: full-screen dark card, username + password fields, "Sign In" button, "Remember me" checkbox, error message on 401, "Register with invite token →" link
  - Write `frontend/src/pages/RegisterPage.tsx`: invite token field (pre-filled from `?token=` query param), display name, username, password, confirm password, "Create Account" button, link back to login
  - Write `frontend/src/utils/auth.ts`: `getToken()`, `setToken()`, `clearToken()`, `isTokenExpired()`, `getUserRole()`, `getDisplayName()` helpers using `localStorage`
  - Write `frontend/src/components/AuthGuard.tsx`: wraps all authenticated routes, redirects to LoginPage if no valid token
  - Update `frontend/src/App.tsx`: add AuthGuard wrapper, add `/login` and `/register` routes
  - Update all `fetch` calls in `frontend/src/api/` to attach `Authorization: Bearer` header; redirect to login on 401
  - Update WebSocket URL in `frontend/src/api/websocket.ts` to append `?token=...`
  - _Requirements: 1.7, 1.8, 1.9, 1.11, 1.15_

- [x] 4. CSS design system and base components
  - Create `frontend/src/styles/design-tokens.css`: extract CSS custom properties from the reference design system at `/home/safsaf/Projects/UAV/frontend/src/resources/theme/` — copy spacing scale, border-radius scale, shadow tokens, neutral color scale, primary/red/green/orange color scales, typography tokens, and card variables; define dark theme (default) and light theme (`[data-theme="light"]`) overrides. No HA/third-party names in comments or variable names visible to users.
  - Create `frontend/src/styles/uav-tokens.css`: UAV-specific semantic aliases — sidebar widths, topbar height, UAV status colors (online/offline/alert/warning), default detection class colors (drone/bird/person/vehicle)
  - Write `frontend/src/components/ui/Card.tsx`: base card component using design token CSS variables
  - Write `frontend/src/components/ui/StatChip.tsx`: colored pill badge using pill border-radius, small font size, `color-mix()` for background tint
  - Write `frontend/src/components/ui/Badge.tsx`: status badge (online/offline/error) using `--uav-color-online/offline/alert`
  - Write `frontend/src/components/ui/Gauge.tsx`: SVG circular gauge for CPU/memory
  - Import both CSS files in `frontend/src/main.tsx`
  - _Requirements: 2.4, 2.5, 2.9, 2.10_

- [x] 5. Sidebar and top bar
  - Write `frontend/src/components/Sidebar.tsx`: collapsible left nav (240px / 64px), nav items with icons and labels, collapse toggle button, persists state in `localStorage`
  - Write `frontend/src/components/TopBar.tsx`: "Anti-UAV Control Center" system name, WebSocket connection status dot, user avatar showing display name initials, logout button that calls `POST /auth/logout` and clears token
  - Write `frontend/src/components/AppShell.tsx`: wraps Sidebar + TopBar + page content area
  - Update `frontend/src/App.tsx`: replace tab nav with AppShell + React Router routes for all pages
  - _Requirements: 2.1, 2.2, 2.3_

- [x] 6. Health reporter — edge device
  - Add `psutil` to `edge/requirements.txt`
  - Write `edge/health_reporter.py`: `HealthReporter` class, background thread, collects CPU/memory via `psutil`, reads `inference_fps` and `frame_id` from `InferenceEngine`, publishes to `uav/health/{device_id}` every 30s
  - Add `current_fps` rolling-average property to `InferenceEngine` (rolling window of last 30 frame timestamps)
  - Add `camera_reconnects` counter to `CameraSource` (incremented on each reconnect)
  - Add `mqtt_reconnects` counter to `MQTTClient` (incremented on each reconnect)
  - Wire `HealthReporter` into `edge/main.py`: start after MQTT client connects, stop on shutdown
  - Add `publish_health(payload_bytes)` method to `MQTTClient`
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 7. Health reporter — tests
  - Write `edge/tests/test_health_reporter.py`: payload contains all required fields, `cpu_percent` in [0,100], `memory_percent` in [0,100], `uptime_s` >= 0, `inference_fps` >= 0
  - Write property test for Health Payload ranges (Property 2): generate random health dicts, assert all field constraints
  - _Requirements: 3.1, 3.2_

- [x] 8. Log publisher — edge device
  - Write `edge/log_publisher.py`: `MQTTLogHandler(logging.Handler)` subclass, formats log record as JSON `Log_Entry`, calls `mqtt_client.publish_log()`
  - Add `publish_log(payload_bytes)` method to `MQTTClient` (topic `uav/log/{device_id}`, QoS 0, no retain)
  - Add `logging.handlers.RotatingFileHandler` to `edge/main.py` (50MB max, 7 backups)
  - Wire `MQTTLogHandler` into root logger at WARNING level in `edge/main.py` after MQTT client starts
  - _Requirements: 7.1, 7.2, 7.3_

- [x] 9. Log publisher — tests
  - Write `edge/tests/test_log_publisher.py`: WARNING record is published, DEBUG record is not published, published payload contains all 5 required fields, `level` is one of WARNING/ERROR/CRITICAL
  - Write property test for Log Entry fields (Property 4): generate random log records, assert required fields present and level valid
  - _Requirements: 7.1, 7.2_

- [x] 10. Cert info in status payload — edge device
  - Update `edge/mqtt_client.py` `_on_connect`: read the client cert file path from config, parse it with Python `ssl` module to extract CN, expiry date, and issuer, add `cert_info: {cn, expires_at, issuer}` to the online status payload
  - Handle missing or unreadable cert gracefully (omit `cert_info` field, log warning)
  - _Requirements: 4.8_

- [x] 11. Aggregation service extensions
  - Extend `DeviceState` dataclass in `main/aggregation/registry.py`: add `health`, `class_counts`, `cert_info`, `log_entries` (list, max 500), `detection_history` (list, max 50) fields
  - Add `update_health(payload)` method to `DeviceRegistry`
  - Add `update_log(entry)` method to `DeviceRegistry` (appends to `log_entries`, no WS push)
  - Update `update_tracking()` to compute `class_counts` by grouping detections by `label` and update `detection_history`
  - Update `update_status()` to extract and store `cert_info` from status payload
  - Update `DeviceState.to_dict()` to include all new fields
  - _Requirements: 3.4, 3.5, 4.9, 5.6, 5.7_

- [x] 12. Aggregation service — new MQTT subscriptions and REST endpoints
  - Update `main/aggregation/mqtt_subscriber.py`: subscribe to `uav/health/#` → `registry.update_health()`, subscribe to `uav/log/#` → `registry.update_log()`
  - Add `GET /logs/{device_id}` endpoint to `main/aggregation/app.py` with `limit` and `level` query params
  - Add `GET /devices/{device_id}/health` endpoint
  - _Requirements: 3.4, 3.6, 7.4, 7.5_

- [x] 13. Aggregation service — tests
  - Write `main/aggregation/tests/test_class_counts.py`: property test for class counts sum (Property 3) — generate random detection arrays, assert `sum(class_counts.values()) == len(detections)`
  - Write unit tests: `update_health` stores payload, `update_log` caps at 500 entries, `class_counts` computed correctly from detections
  - _Requirements: 5.6, 5.7, 7.4_

- [x] 14. Backend data bridge service
  - Write `main/ha_bridge/bridge.py`: paho-mqtt client, subscribes to `uav/tracking/#`, `uav/status/#`, `uav/health/#`, `uav/sensor/#`, publishes MQTT Discovery config on first message per device, publishes state updates on every message. No UI, no frontend references.
  - Implement discovery config builder for all entity types: binary_sensor (uav_detected), and sensors (detection_count, active_model, device_status, cpu_percent, inference_fps, last_detection, compass_bearing, per-class counts)
  - Implement exponential backoff reconnect; re-publish all discovery configs on reconnect
  - Write `main/ha_bridge/Dockerfile`: FROM python:3.11-slim, installs paho-mqtt, copies bridge.py
  - Add `ha_bridge` service to `docker/docker-compose.yml` with `MQTT_HOST: mosquitto`, `MQTT_PORT: 1883`, depends_on mosquitto
  - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.8, 11.9_

- [x] 15. Backend data bridge — tests
  - Write `main/ha_bridge/tests/test_bridge.py`: discovery config contains required fields (unique_id, name, state_topic, device block), state update published after tracking message, binary_sensor ON when detection_count > 0
  - Write property test for discovery config fields (Property 5): generate random device IDs, assert all required discovery config fields present
  - _Requirements: 11.3, 11.6_

- [x] 16. Frontend — DeviceCard component
  - Write `frontend/src/components/DeviceCard.tsx`: Card wrapper, status Badge, device ID, uptime formatted as `Xh Ym`, active model StatChip, per-class detection StatChips using `getClassColor()`, last detection timestamp, "View" button (navigates to DeviceDetailPage), "Stream" button (sends start_stream command)
  - Write `frontend/src/utils/classColors.ts`: `getClassColor(label, profileColors?)` with default color map
  - Write `frontend/src/utils/formatUptime.ts`: converts seconds to `Xh Ym` string
  - _Requirements: 2.6, 5.1, 5.3_

- [x] 17. Frontend — Overview page
  - Write `frontend/src/pages/OverviewPage.tsx`: 4 summary stat Cards (Total Devices, Online Now, Active Detections, Alerts Today), responsive CSS grid of DeviceCard components
  - Replace existing `DeviceDashboard` component usage with OverviewPage in the router
  - _Requirements: 2.7_

- [x] 18. Frontend — class color system and overlay fix
  - Update `frontend/src/components/TrackingOverlay.tsx`: use `videoRef.current.videoWidth/videoHeight` via `loadedmetadata` event for scale factors, attach ResizeObserver to canvas, color bounding boxes by class using `getClassColor()`, add class legend overlay in corner
  - Update `frontend/src/types/index.ts`: add `class_counts: Record<string, number>` to `DeviceState`
  - _Requirements: 5.1, 5.2, 8.3, 8.4, 8.5_

- [x] 19. Frontend — live feed auto-start fix
  - Update `frontend/src/components/LiveFeedGrid.tsx` (now `LiveFeedsPage`): send `start_stream` on mount for all online devices, track active streams in a `Set`, add "Waiting for stream…" spinner state, add "Stream interrupted" error state distinct from waiting state
  - Add Intersection Observer to DeviceCard thumbnail to auto-send `start_stream` when thumbnail scrolls into view
  - Add `TURN_SERVER_URL` support to `RTCPeerConnection` config in `LiveFeedGrid.tsx`
  - _Requirements: 8.1, 8.2, 8.6, 8.7, 8.8_

- [x] 20. Frontend — map panel
  - Write `frontend/src/components/MapPanel.tsx`: slide-in right panel (320px wide, full-width on mobile), X dismiss button, device header with lat/lon copy button, embedded FeedCell (auto-starts on open), ClassBreakdown section, HealthSnapshot section, SensorDisplay with compass rose SVG, PtzMiniControls (conditional on PTZ enabled), quick action buttons
  - Write `frontend/src/components/CompassRose.tsx`: SVG compass rose that rotates based on bearing value
  - Update `frontend/src/components/MapView.tsx`: replace Leaflet Popup with MapPanel trigger on marker click, pass device state to panel
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10_

- [x] 21. Frontend — Device Detail page
  - Write `frontend/src/pages/DeviceDetailPage.tsx`: full-page view with sections: header (ID, status, uptime), HealthGauges (CPU Gauge, memory Gauge, FPS, frames processed), CertInfo (CN, expiry, issuer, warning if < 30 days), ConnectionTimeline (MQTT events), ModelInfo (active model, camera mode, all profiles), DetectionHistory (last 50 detections table with timestamp, label, confidence, bbox)
  - Write `frontend/src/components/HealthGauges.tsx`: circular gauge components using SVG
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

- [x] 22. Frontend — Logs page
  - Write `frontend/src/pages/LogsPage.tsx`: filter bar (device dropdown, level dropdown, time range), log table with color-coded rows (WARNING=amber, ERROR=orange, CRITICAL=red), auto-scroll to latest, pause on hover, "Export to CSV" button
  - Add `GET /logs/{device_id}` call to `frontend/src/api/commands.ts`
  - _Requirements: 7.6, 7.7, 7.8, 7.9_

- [x] 23. Frontend — Settings page
  - Write `frontend/src/pages/SettingsPage.tsx`: card-based layout with sections:
    - MQTT Config card (read-only display of current broker settings)
    - Cert Paths card (display cert paths from config)
    - Model Profiles card (list all profiles per device)
    - Theme toggle card (dark/light, persists in localStorage)
    - Users card (Admin only): user list table with display name, username, role, created_at, last_login, deactivate button; "Generate Invite" button with role dropdown and expiry dropdown; shows generated token with copy button and shareable link (`/register?token=...`)
    - Audit Log card (Admin only): last 100 user actions table with username, action, device_id, timestamp; filter by user and device dropdowns
  - Add `GET /auth/users`, `POST /auth/invite`, `DELETE /auth/users/{username}`, `GET /audit` calls to `frontend/src/api/auth.ts`
  - _Requirements: 1.13, 1.14, 1.16, 1.17, 1.18, 1.19, 2.8, 2.9_

- [x] 24. Frontend — PWA manifest and service worker
  - Write `frontend/public/manifest.json`: app name "Anti-UAV Control Center", short name "UAV Control", icons (192px and 512px), display standalone, theme_color and background_color matching dark theme
  - Create `frontend/public/icons/icon-192.png` and `icon-512.png` (radar/UAV detection icon — no third-party branding)
  - Write `frontend/src/sw.ts`: service worker that caches app shell (HTML, CSS, JS) using Cache API, serves cached shell on offline
  - Register service worker in `frontend/src/main.tsx`
  - Add `<link rel="manifest">` to `frontend/index.html`
  - _Requirements: 12.1, 12.2_

- [x] 25. Simplified main launcher
  - Rewrite `launcher_main.py`: 3 primary fields (MQTT Port, Control Center Port, Remote Access Mode dropdown), collapsible Advanced section, service health panel polling `docker compose ps` every 5s with colored status dots, "Open Control Center" button, tabbed layout with "Stack" tab and "Certs" tab
  - Implement Cert_Wizard in the "Certs" tab: Server IP field, Device IDs field, "Generate" button runs `gen_certs.sh` and streams output, cert status table reads generated files and shows CN/expiry/badge, "Copy to Device" button per row runs SCP
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 10.1, 10.2, 10.3, 10.4, 10.5_

- [x] 26. Simplified edge launcher
  - Rewrite `launcher_edge.py`: 3 primary fields (Camera URL, Main Device IP, Model .pt path), collapsible Advanced section with TLS cert paths (auto-detect from `./secrets/`), PTZ/sensor/estimator settings, "Test Camera" button (captures one frame, shows thumbnail), "Test MQTT" button (attempts connection, shows result within 3s)
  - _Requirements: 9.6, 9.7, 9.8, 9.9, 9.10_

- [x] 27. Documentation — Android and WireGuard
  - Write `docker/wireguard/android-peer.md`: step-by-step guide for generating an Android WireGuard peer config, importing via QR code in the WireGuard Android app, and accessing the Anti-UAV Control Center (port 8080) remotely
  - Write a section in `INSTRUCTIONS.md` for installing the Anti-UAV Control Center PWA on Android (Chrome → Add to Home Screen → installs as standalone app with its own icon)
  - _Requirements: 12.3, 12.4_

- [x] 28. Checkpoint — all tests pass
  - Run `pytest edge/tests/ main/aggregation/tests/ main/control-center/tests/ main/ha_bridge/tests/ --hypothesis-seed=0 -v`
  - Verify Docker Compose stack starts cleanly with all new services
  - Verify HA Bridge entities appear in Home Assistant after stack start
  - Verify PWA installs on Android Chrome
  - Ask the user if questions arise before proceeding

## Notes

- Tasks 1–3 (auth) can be done independently of tasks 4–5 (UI shell) — both are needed before page-level frontend tasks
- Tasks 6–13 (edge health/logs + aggregation) must be done before tasks 16–22 (frontend pages that consume the new data)
- Task 14 (HA Bridge) is fully independent — can be done at any point after task 12
- Tasks 25–26 (launchers) are fully independent of all other tasks
- The existing `anti-uav-detection-system` spec tasks remain valid and unaffected
