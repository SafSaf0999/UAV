# Requirements Document

## Introduction

Anti-UAV Control Center v3 is a set of enhancements to the existing distributed anti-UAV detection system. The system consists of edge devices running YOLO inference that publish detections over MQTT to a main device running a Docker stack (Mosquitto broker, FastAPI aggregation, React frontend, Node.js WebRTC signaling). V3 adds twelve features: simplified MQTT authentication, token and session management UIs, edge config push, detection history export, per-device alert thresholds, multi-device PTZ follow, notification webhooks, edge offline detection, improved launchers, an Electron desktop app, and a bounding box color scheme update.

## Glossary

- **Edge_Device**: A remote device running YOLO inference and publishing detections over MQTT.
- **Main_Device**: The central server running the Docker stack (broker, aggregation, control-center, frontend).
- **Aggregation_Service**: The FastAPI service that subscribes to MQTT, maintains device state, and exposes REST/WebSocket APIs.
- **Control_Center**: The FastAPI service that handles authentication, proxies API calls, and serves the React frontend.
- **MQTT_Broker**: The Mosquitto broker that routes messages between edge devices and the aggregation service.
- **Auth_DB**: The SQLite database (`auth.db`) storing users, invite tokens, and audit log entries.
- **JWT**: JSON Web Token used for authenticating frontend users to the Control_Center.
- **Device_Registry**: The in-memory state store in the Aggregation_Service tracking all known edge device states.
- **PTZ**: Pan-Tilt-Zoom camera control.
- **Webhook**: An HTTP callback URL that receives JSON event notifications.
- **Launcher**: A tkinter GUI application (`launcher_main.py` or `launcher_edge.py`) for configuring and starting services.
- **Electron_App**: A desktop application wrapping the React frontend in an Electron shell.
- **Bounding_Box**: A rectangle drawn on the video overlay indicating a detected object.
- **Health_Message**: A periodic MQTT message published by an edge device reporting CPU, memory, and inference metrics.
- **Invite_Token**: A one-time-use token that allows a new user to register an account.
- **Session**: An active JWT issued to a logged-in user, stored in the Auth_DB.
- **Confidence**: A float in [0, 1] representing the model's certainty about a detection.

---

## Requirements

### Requirement 1: MQTT Username/Password Authentication

**User Story:** As a system administrator, I want edge devices to authenticate to the MQTT broker using username and password instead of client certificates, so that device provisioning is simpler and does not require distributing per-device TLS certificates.

#### Acceptance Criteria

1. WHEN an Edge_Device connects to the MQTT_Broker, THE MQTT_Broker SHALL authenticate the device using a username equal to the device's `device_id` and a pre-shared password from the device's config.
2. THE MQTT_Broker SHALL maintain TLS encryption using a server certificate only, without requiring client certificates.
3. THE Edge_Device SHALL read `mqtt.username` and `mqtt.password` from its `config.yaml` and pass them to the MQTT connection.
4. IF `mqtt.username` is absent from the Edge_Device config, THEN THE Edge_Device SHALL log a warning and attempt an unauthenticated connection.
5. THE `config.yaml` schema SHALL support `mqtt.username` and `mqtt.password` fields and SHALL NOT require `mqtt.tls.client_cert` or `mqtt.tls.client_key`.
6. THE `gen_certs.sh` script SHALL generate only the CA certificate and server certificate, and SHALL NOT generate per-device client certificates.
7. WHEN `MQTT_AUTH_MODE` is set to `password`, THE MQTT_Broker entrypoint SHALL configure Mosquitto with `require_certificate false` and a password file.
8. THE `docker-compose.yml` SHALL support a `MQTT_PASSWORD_FILE` environment variable pointing to the Mosquitto password file in the secrets volume.
9. THE Edge_Launcher GUI SHALL replace the CA cert, client cert, and client key fields with a single password field for MQTT authentication.

---

### Requirement 2: Token Management UI

**User Story:** As an admin user, I want to view and manage all invite tokens from the Settings page, so that I can track which tokens have been used, revoke unused ones, and share registration links.

#### Acceptance Criteria

1. THE Control_Center SHALL expose a `GET /api/tokens` endpoint that returns all invite tokens with fields: `token`, `role`, `created_by`, `created_at`, `expires_at`, `status` (one of `pending`, `used`, `expired`), and `used_by` (username if consumed, otherwise null).
2. WHEN a token's `used_by` is not null, THE Control_Center SHALL set its `status` to `used`.
3. WHEN a token's `expires_at` is before the current time and `used_by` is null, THE Control_Center SHALL set its `status` to `expired`.
4. WHEN a token has not been used and has not expired, THE Control_Center SHALL set its `status` to `pending`.
5. THE Settings page SHALL include a "Tokens" tab visible only to admin users.
6. WHEN an admin user views the Tokens tab, THE Tokens_Tab SHALL display a table with columns: Token, Role, Created By, Created At, Expires At, Status, Used By.
7. WHEN an admin user clicks "Revoke" on a pending token, THE Control_Center SHALL delete that token from the Auth_DB and THE Tokens_Tab SHALL remove it from the table.
8. WHEN an admin user clicks "Copy Link" on a pending token, THE Tokens_Tab SHALL copy the full registration URL (`/register?token=<value>`) to the clipboard.
9. THE `DELETE /api/tokens/{token}` endpoint SHALL only allow deletion of tokens with `status` equal to `pending`; IF the token is `used` or `expired`, THEN THE Control_Center SHALL return HTTP 400.

---

### Requirement 3: Session Management UI

**User Story:** As an admin user, I want to view and revoke active user sessions from the Settings page, so that I can terminate compromised or stale logins.

#### Acceptance Criteria

1. THE Auth_DB SHALL contain a `sessions` table with columns: `jti` (TEXT PRIMARY KEY), `username`, `display_name`, `login_time`, `last_seen`, `user_agent`, `expires_at`.
2. WHEN a user successfully logs in, THE Control_Center SHALL insert a row into the `sessions` table with the JWT's `jti`, the current timestamp as `login_time` and `last_seen`, and the `User-Agent` header value.
3. WHEN an authenticated request is received, THE Control_Center SHALL update the `last_seen` timestamp for the matching `jti` in the `sessions` table.
4. WHEN a JWT is revoked via logout or admin revocation, THE Control_Center SHALL delete the corresponding row from the `sessions` table.
5. THE Control_Center SHALL expose a `GET /api/sessions` endpoint (admin only) returning all active sessions with fields: `jti`, `username`, `display_name`, `login_time`, `last_seen`, `user_agent`.
6. THE Control_Center SHALL expose a `DELETE /api/sessions/{jti}` endpoint (admin only) that invalidates the specified session by adding its `jti` to the in-memory blocklist and deleting the row from the `sessions` table.
7. THE Settings page SHALL include a "Sessions" tab visible only to admin users.
8. WHEN an admin user views the Sessions tab, THE Sessions_Tab SHALL display a table with columns: Username, Display Name, Login Time, Last Seen, User Agent, and a Revoke button.
9. WHEN an admin user clicks "Revoke" on a session, THE Sessions_Tab SHALL call `DELETE /api/sessions/{jti}` and remove the row from the table.

---

### Requirement 4: Edge Device Config Push

**User Story:** As an operator, I want to push configuration changes to an edge device from the Device Detail page, so that I can update camera source, FPS, and active model without restarting the device.

#### Acceptance Criteria

1. THE Aggregation_Service SHALL support a new MQTT command action `update_config` with a JSON payload containing any subset of: `camera_source`, `fps`, `active_model`.
2. WHEN the Edge_Device receives an `update_config` command, THE Edge_Device SHALL apply the changes to its running components without requiring a process restart.
3. WHEN `active_model` is included in an `update_config` command, THE Edge_Device SHALL hot-swap the inference model using the existing `ModelManager.hot_swap()` method.
4. WHEN `camera_source` or `fps` is included in an `update_config` command, THE Edge_Device SHALL update the `CameraSource` with the new values.
5. IF an `update_config` command contains an unrecognized field, THEN THE Edge_Device SHALL ignore that field and apply the recognized fields.
6. THE Device_Detail_Page SHALL include an "Edit Config" panel with fields for `camera_source`, `fps`, and `active_model`.
7. WHEN an operator submits the Edit Config form, THE Device_Detail_Page SHALL POST to `/api/command/{device_id}` with `action: "update_config"` and the changed fields.
8. THE Control_Center SHALL proxy `POST /api/command/{device_id}` to the Aggregation_Service and require a valid JWT.

---

### Requirement 5: Detection History Export

**User Story:** As an analyst, I want to export detection history for a specific device and time range as a CSV file, so that I can perform offline analysis.

#### Acceptance Criteria

1. THE Aggregation_Service SHALL persist detection events to a SQLite database with columns: `id`, `device_id`, `timestamp`, `label`, `confidence`, `bbox_x`, `bbox_y`, `bbox_w`, `bbox_h`, `track_id`.
2. WHEN a tracking payload is received, THE Aggregation_Service SHALL insert each detection into the detections database.
3. THE Aggregation_Service SHALL expose `GET /devices/{device_id}/detections/export` with query parameters `from` (ISO 8601 datetime), `to` (ISO 8601 datetime), and `format` (default `csv`).
4. WHEN `format=csv` is requested, THE Aggregation_Service SHALL return a CSV file with a header row and one row per detection within the time range.
5. IF no detections exist for the requested range, THEN THE Aggregation_Service SHALL return an empty CSV with only the header row.
6. THE Logs_Page SHALL include an "Export Detections" button that opens a date range picker with `from` and `to` fields and a device selector.
7. WHEN an analyst submits the export form, THE Logs_Page SHALL trigger a file download by navigating to the export endpoint URL with the selected parameters.

---

### Requirement 6: Per-Device Alert Thresholds

**User Story:** As an operator, I want to configure per-device alert thresholds so that the system only triggers alerts when detections meet minimum confidence, consecutive frame count, and class criteria.

#### Acceptance Criteria

1. THE Aggregation_Service SHALL maintain per-device threshold configuration with fields: `min_confidence` (float, default 0.5), `consecutive_frames` (int, default 1), `alert_classes` (list of strings, default `["drone"]`).
2. WHEN a tracking payload is received, THE Aggregation_Service SHALL evaluate each detection against the device's threshold configuration before deciding to push a WebSocket alert.
3. WHEN a detection's `confidence` is below `min_confidence`, THE Aggregation_Service SHALL NOT emit a WebSocket alert for that detection.
4. WHEN a detection class is not in `alert_classes`, THE Aggregation_Service SHALL NOT emit a WebSocket alert for that detection.
5. WHEN a detection meets `min_confidence` and `alert_classes` criteria for at least `consecutive_frames` consecutive tracking payloads, THE Aggregation_Service SHALL emit a WebSocket alert event.
6. THE Control_Center SHALL expose `GET /api/devices/{device_id}/thresholds` and `PUT /api/devices/{device_id}/thresholds` endpoints (admin only).
7. THE Settings_Page SHALL include a per-device threshold editor accessible from the device list, with fields for `min_confidence`, `consecutive_frames`, and `alert_classes`.
8. WHEN an admin saves threshold changes, THE Settings_Page SHALL call `PUT /api/devices/{device_id}/thresholds` with the updated values.

---

### Requirement 7: Multi-Device PTZ Follow

**User Story:** As an operator, I want a "leader" edge device's detections to automatically drive PTZ commands to all configured "follower" devices, so that multiple cameras can track the same target.

#### Acceptance Criteria

1. THE edge `config.yaml` SHALL support a `ptz.follow_leader` field containing the `device_id` of the leader device (e.g., `edge-01`).
2. WHEN the Aggregation_Service receives a tracking payload from the leader device containing at least one detection, THE Aggregation_Service SHALL compute a bearing angle from the leader's GPS coordinates and the bounding box center position.
3. WHEN a bearing is computed, THE Aggregation_Service SHALL publish a PTZ pan command to `uav/ptz/{follower_device_id}` for every device configured with `ptz.follow_leader` equal to the leader's `device_id`.
4. THE PTZ follow command payload SHALL include `command: "pan_to_bearing"` and `bearing_deg` (float, 0–360).
5. THE Edge_Device SHALL handle the `pan_to_bearing` PTZ command by delegating to the `PTZController`.
6. THE system SHALL include an `edge_sim.py` script that simulates a second edge device publishing health and tracking payloads over MQTT, enabling PTZ follow testing without physical hardware.
7. WHERE `ptz.follow_leader` is configured, THE Edge_Device SHALL include the field in its status payload so the Aggregation_Service can build the follower map.

---

### Requirement 8: Notification Webhooks

**User Story:** As an operator, I want to configure HTTP webhook URLs that receive notifications for detection alerts, device online, and device offline events, so that I can integrate the system with external alerting tools.

#### Acceptance Criteria

1. THE Auth_DB SHALL contain a `webhooks` table with columns: `id` (INTEGER PRIMARY KEY), `url` (TEXT), `events` (TEXT, comma-separated list), `secret` (TEXT), `enabled` (INTEGER).
2. WHEN a `detection_alert` event occurs, THE Aggregation_Service SHALL POST a JSON payload to all enabled webhooks subscribed to `detection_alert`.
3. WHEN a `device_online` event occurs, THE Aggregation_Service SHALL POST a JSON payload to all enabled webhooks subscribed to `device_online`.
4. WHEN a `device_offline` event occurs, THE Aggregation_Service SHALL POST a JSON payload to all enabled webhooks subscribed to `device_offline`.
5. THE webhook POST payload SHALL include fields: `event` (event type string), `device_id`, `timestamp` (ISO 8601), and event-specific data.
6. WHEN a webhook `secret` is non-empty, THE Aggregation_Service SHALL include an `X-UAV-Signature` header containing the HMAC-SHA256 of the payload body using the secret.
7. IF a webhook POST fails (non-2xx response or network error), THEN THE Aggregation_Service SHALL log the failure and SHALL NOT retry.
8. THE Settings_Page SHALL include a "Notifications" tab with a form to add webhooks (URL, events checkboxes, secret) and a table listing existing webhooks with enable/disable toggle, test, and delete actions.
9. WHEN an operator clicks "Test" on a webhook, THE Control_Center SHALL POST a test payload with `event: "test"` to that webhook URL and return the HTTP response status to the frontend.
10. THE Control_Center SHALL expose `GET /api/webhooks`, `POST /api/webhooks`, `PUT /api/webhooks/{id}`, and `DELETE /api/webhooks/{id}` endpoints (admin only).

---

### Requirement 9: Edge Device Offline Detection

**User Story:** As an operator, I want the system to automatically detect when an edge device stops sending health messages and mark it as "health timeout", so that I can distinguish between a clean shutdown and an unexpected failure.

#### Acceptance Criteria

1. THE Aggregation_Service SHALL track the timestamp of the last received Health_Message for each device.
2. WHEN more than 60 seconds have elapsed since the last Health_Message for a device that was previously `online`, THE Aggregation_Service SHALL set that device's status to `health_timeout`.
3. WHEN a device transitions to `health_timeout`, THE Aggregation_Service SHALL emit a `device_offline` webhook event.
4. WHEN a new Health_Message is received from a device in `health_timeout` state, THE Aggregation_Service SHALL restore the device's status to `online`.
5. THE Device_Registry SHALL distinguish between `offline` (clean LWT-based disconnect), `health_timeout` (missed heartbeat), and `online` statuses.
6. THE frontend Dashboard SHALL display a distinct visual indicator (amber/yellow color) for devices in `health_timeout` state, separate from the red indicator used for `offline`.
7. THE Aggregation_Service SHALL run a background task that checks health timestamps every 10 seconds.

---

### Requirement 10: Improved Launchers

**User Story:** As a developer or operator, I want the launcher GUIs to have a tabbed layout with Config, Status, and Logs tabs, a dark theme, live log tailing, and per-service controls, so that managing the system is easier and more informative.

#### Acceptance Criteria

1. THE Main_Launcher SHALL use a tabbed layout with tabs: Config, Status, and Logs.
2. THE Edge_Launcher SHALL use a tabbed layout with tabs: Config, Status, and Logs.
3. WHILE the Main_Launcher is open, THE Status_Tab SHALL display per-service health indicators (green dot for running, red dot for stopped) for each Docker service.
4. WHILE the Edge_Launcher is open, THE Status_Tab SHALL display the current inference process status and last-seen MQTT connection state.
5. WHEN a new log line is produced, THE Logs_Tab SHALL append it to a scrolling text area and auto-scroll to the bottom.
6. THE Main_Launcher Config_Tab SHALL allow per-service start and stop, not only "Start All".
7. THE Edge_Launcher Config_Tab SHALL include a "Test Connection" button that verifies MQTT connectivity using the configured username and password.
8. THE Edge_Launcher Config_Tab SHALL include a camera preview thumbnail that displays a single captured frame from the configured camera source.
9. THE launchers SHALL use a dark color scheme matching the control center (`#0f172a` background, `#1e293b` card, `#3b82f6` accent).
10. THE Main_Launcher SHALL retain all existing functionality from the current implementation (cert generation, env file management, Docker compose control).

---

### Requirement 11: Electron Desktop App

**User Story:** As an operator, I want a native desktop application that wraps the React frontend and automatically manages the Docker stack, so that I can run the control center without using a terminal.

#### Acceptance Criteria

1. THE Electron_App SHALL embed a browser window that loads the React frontend at `http://localhost:8080` after the Docker stack starts.
2. WHEN the Electron_App launches, THE Electron_App SHALL start the Docker Compose stack in the background using `docker compose up -d`.
3. WHEN the Docker stack is ready (control-center port 8080 responds), THE Electron_App SHALL show the embedded browser window.
4. THE Electron_App SHALL display a system tray icon with menu items: "Open", "Stop Stack", and "Quit".
5. WHEN "Stop Stack" is selected from the tray, THE Electron_App SHALL run `docker compose down` and update the tray icon state.
6. WHEN "Quit" is selected from the tray, THE Electron_App SHALL run `docker compose down` and then exit the process.
7. THE Electron_App SHALL be packaged as an AppImage for universal Linux distribution.
8. THE Electron_App SHALL include an Arch Linux PKGBUILD file for installation via `makepkg`.
9. WHILE the Docker stack is starting, THE Electron_App SHALL display a loading screen with status text.

---

### Requirement 12: Bounding Box Color Scheme Update

**User Story:** As an operator, I want bounding boxes to use a consistent color scheme that distinguishes birds from drones and high-confidence from low-confidence drone detections, so that I can quickly assess threat level at a glance.

#### Acceptance Criteria

1. WHEN a detection has label `bird` (any confidence), THE TrackingOverlay SHALL render the bounding box in green (`#22c55e`).
2. WHEN a detection has label `drone` and confidence ≥ 0.5, THE TrackingOverlay SHALL render the bounding box in red (`#ef4444`).
3. WHEN a detection has label `drone` and confidence < 0.5, THE TrackingOverlay SHALL render the bounding box in orange (`#f97316`).
4. THE `getClassColor` utility function SHALL accept a `confidence` parameter in addition to `label` and `profileColors`, and SHALL apply the drone confidence split logic.
5. THE overlay legend SHALL reflect the updated color scheme, showing green for bird, red for high-confidence drone, and orange for low-confidence drone.
6. THE CSS variable `--uav-class-drone` SHALL be replaced by the confidence-based logic; the `--uav-class-bird` variable SHALL be updated to `#22c55e`.

---

### Requirement 13: WebRTC Live Feed Black Screen Fix

**User Story:** As an operator, I want the WebRTC live feed to display the actual camera image instead of a black screen, so that I can monitor the edge device camera feed reliably.

#### Acceptance Criteria

1. WHEN `pc.ontrack` fires and `videoRef.current.srcObject` is set, THE `useWebRTCStream` hook SHALL call `videoRef.current.play()` and catch any autoplay policy errors.
2. THE `streamState` SHALL transition to `"connected"` only after the video element emits a `canplay` or `loadedmetadata` event, not immediately when `ontrack` fires.
3. THE `CameraVideoTrack._get_frame()` method SHALL block until a real frame is available in the queue rather than returning a black frame on timeout, using a loop with a short sleep that respects the stop condition.
4. THE `WebRTCStreamer` SHALL NOT add the video track to the `RTCPeerConnection` until at least one real frame has been placed in the frame queue by the `CameraSource`.
5. WHEN the camera source is reconnecting and the frame queue is empty, THE `CameraVideoTrack` SHALL send the last successfully received frame rather than a black frame, falling back to a black frame only if no frame has ever been received.
6. THE `FeedCell` component SHALL attach an `onCanPlay` handler to the `<video>` element that calls `.play()` to ensure playback starts regardless of autoplay policy.

---

### Requirement 14: IP Webcam Remote Control

**User Story:** As an operator, I want full remote control of the IP Webcam phone camera from the main control center — including zoom, torch, focus, camera flip, night vision, video resolution, ISO sensitivity, manual exposure, frame duration, and aperture — so that I can adjust all camera parameters remotely without physically accessing the edge device or phone.

#### Acceptance Criteria

**Configuration:**
1. THE edge `config.yaml` SHALL support an `ipwebcam.url` field containing the base HTTP URL of the IP Webcam app (e.g. `http://192.168.1.x:8080`).
2. WHEN the Edge_Device starts and `ipwebcam.url` is configured, THE Edge_Device SHALL fetch `GET {ipwebcam.url}/status.json?show_avail=1` to discover available settings and their valid ranges, and SHALL publish the result to `uav/ipwebcam/capabilities/{device_id}`.
3. THE Aggregation_Service SHALL store the capabilities payload and include it in the device state so the frontend can render only the controls supported by the connected phone.

**MQTT Command Handling:**
4. THE Edge_Device SHALL handle a new MQTT command action `ipwebcam_control` with a JSON payload containing `setting` (string) and optionally `value` (string or number).
5. WHEN the Edge_Device receives an `ipwebcam_control` command, THE Edge_Device SHALL forward the command to the IP Webcam HTTP API using the configured `ipwebcam.url`.
6. IF `ipwebcam.url` is not configured, THEN THE Edge_Device SHALL log a warning and return an error response for any `ipwebcam_control` command.

**Supported Settings — Basic Controls:**
7. THE Edge_Device SHALL support `setting: zoom` (value: 0–100) by calling `GET {ipwebcam.url}/zoom?level={value}`.
8. THE Edge_Device SHALL support `setting: focus` (no value) by calling `GET {ipwebcam.url}/focus`.
9. THE Edge_Device SHALL support `setting: torch` (value: `on`/`off`) by calling `GET {ipwebcam.url}/settings/torch?set={value}`.
10. THE Edge_Device SHALL support `setting: ffc` (value: `on`/`off`) by calling `GET {ipwebcam.url}/settings/ffc?set={value}`.
11. THE Edge_Device SHALL support `setting: night_vision` (value: `on`/`off`) by calling `GET {ipwebcam.url}/settings/night_vision?set={value}`.
12. THE Edge_Device SHALL support `setting: overlay` (value: `on`/`off`) by calling `GET {ipwebcam.url}/settings/overlay?set={value}`.
13. THE Edge_Device SHALL support `setting: exposure_lock` (value: `on`/`off`) by calling `GET {ipwebcam.url}/settings/exposure_lock?set={value}`.
14. THE Edge_Device SHALL support `setting: whitebalance_lock` (value: `on`/`off`) by calling `GET {ipwebcam.url}/settings/whitebalance_lock?set={value}`.
15. THE Edge_Device SHALL support `setting: video_recording` (value: `on`/`off`) by calling `GET {ipwebcam.url}/settings/video_recording?set={value}`.
16. THE Edge_Device SHALL support `setting: quality` (value: 0–100) by calling `GET {ipwebcam.url}/settings/quality?set={value}`.

**Supported Settings — Camera2 / Advanced Controls:**
17. THE Edge_Device SHALL support `setting: video_size` (value: e.g. `1920x1080`) by calling `GET {ipwebcam.url}/settings/video_size?set={value}`.
18. THE Edge_Device SHALL support `setting: manual_sensor` (value: `on`/`off`) by calling `GET {ipwebcam.url}/settings/camera2_manual_sensor?set={value}`.
19. THE Edge_Device SHALL support `setting: iso` (value: integer, e.g. 100–3200) by calling `GET {ipwebcam.url}/settings/camera2_sensor_sensitivity?set={value}`.
20. THE Edge_Device SHALL support `setting: exposure_time` (value: integer nanoseconds) by calling `GET {ipwebcam.url}/settings/camera2_sensor_exposure_time?set={value}`.
21. THE Edge_Device SHALL support `setting: frame_duration` (value: integer nanoseconds) by calling `GET {ipwebcam.url}/settings/camera2_sensor_frame_duration?set={value}`.
22. THE Edge_Device SHALL support `setting: aperture` (value: float f-number) by calling `GET {ipwebcam.url}/settings/camera2_lens_aperture?set={value}`.
23. WHEN `manual_sensor` is `off`, THE frontend SHALL disable the ISO, exposure_time, frame_duration, and aperture controls and display them as read-only.

**Supported Settings — Additional Controls:**
24. THE Edge_Device SHALL support `setting: crop_x` (value: 0–100) by calling `GET {ipwebcam.url}/settings/crop?set={value},Y` where Y is the current crop_y value.
25. THE Edge_Device SHALL support `setting: crop_y` (value: 0–100) by calling `GET {ipwebcam.url}/settings/crop?set=X,{value}` where X is the current crop_x value.
26. THE Edge_Device SHALL support `setting: focus_mode` (value: string, e.g. `auto`, `macro`, `infinity`, `fixed`) by calling `GET {ipwebcam.url}/settings/focus_mode?set={value}`.

**Snapshot:**
27. THE Edge_Device SHALL support `setting: snapshot` (no value) by fetching `GET {ipwebcam.url}/photo.jpg`, encoding the image as base64, and publishing it to `uav/snapshot/{device_id}`.
28. THE Edge_Device SHALL support `setting: snapshot_af` (no value) by fetching `GET {ipwebcam.url}/photoaf.jpg` (autofocus before capture) and publishing the result identically to `snapshot`.
29. THE Aggregation_Service SHALL forward the snapshot payload to the frontend via WebSocket.
30. WHEN the operator clicks "Snapshot", THE Device_Detail_Page SHALL display the received snapshot image in a modal dialog with a download button.

**Sensor Polling:**
31. THE Aggregation_Service SHALL periodically (every 30 seconds) publish an `ipwebcam_sensors` MQTT command to the edge device.
32. WHEN the Edge_Device receives `ipwebcam_sensors`, THE Edge_Device SHALL fetch `GET {ipwebcam.url}/sensors.json` and publish the result to `uav/ipwebcam/sensors/{device_id}`.
33. THE Aggregation_Service SHALL include the sensor data in the device state WebSocket payload.
34. THE Device_Detail_Page SHALL display IP Webcam sensor data (battery_level, battery_temp, light, motion, pressure, audio_connections) in the health section when available.

**Frontend UI:**
35. THE Device_Detail_Page SHALL include an "IP Webcam Controls" panel visible only when `ipwebcam.url` is configured for the device.
36. THE IP Webcam Controls panel SHALL be organised into sections:
    - **Stream**: zoom slider, crop X/Y sliders, video resolution dropdown, quality slider
    - **Camera**: torch toggle, front/back camera toggle, night vision toggle, overlay toggle
    - **Focus**: focus mode dropdown (populated from capabilities), focus trigger button, focused snapshot button
    - **Exposure**: manual sensor toggle, ISO slider, exposure time input (in ms), frame duration input (in ms), aperture input, exposure lock toggle, white balance lock toggle
    - **Recording**: video recording toggle, snapshot button
37. THE video resolution dropdown SHALL be populated from the capabilities payload so only resolutions supported by the connected phone are shown.
38. THE ISO slider range and focus mode options SHALL be populated from the capabilities payload min/max/available values.
39. WHEN a control is changed, THE Device_Detail_Page SHALL immediately send the corresponding `ipwebcam_control` MQTT command via the existing `/api/command/{device_id}` endpoint.
40. THE exposure time and frame duration inputs SHALL display values in milliseconds in the UI and convert to nanoseconds when sending the MQTT command.
