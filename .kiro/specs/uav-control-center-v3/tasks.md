# Implementation Plan: Anti-UAV Control Center v3

## Overview

Incremental enhancements to the existing v2 system. Tasks are ordered to build on each other: backend schema and edge changes first, then aggregation service, then control-center API, then frontend, then launchers and Electron app. Each task references the specific requirement clauses it satisfies.

## Tasks

- [x] 1. MQTT username/password authentication
  - [x] 1.1 Update `edge/config.py` to expose `mqtt.username` and `mqtt.password` fields; log a warning when `mqtt.username` is absent
    - _Requirements: 1.3, 1.4, 1.5_
  - [ ]* 1.2 Write property test for MQTT credential passing (Property 1)
    - **Property 1: MQTT client uses config credentials**
    - **Validates: Requirements 1.3**
    - Use Hypothesis: `@given(username=st.text(min_size=1), password=st.text())`
  - [x] 1.3 Update `edge/mqtt_client.py` to call `username_pw_set` as the primary auth path when `mqtt.username` is present; remove client-cert requirement
    - _Requirements: 1.1, 1.2, 1.3_
  - [ ]* 1.4 Write unit tests for `mqtt_client.py` credential handling
    - Verify `username_pw_set` is called with config values; verify warning logged when username absent
    - _Requirements: 1.3, 1.4_
  - [x] 1.5 Update `docker/mosquitto` entrypoint and `docker-compose.yml` to support `MQTT_AUTH_MODE=password` and `MQTT_PASSWORD_FILE` env var
    - _Requirements: 1.7, 1.8_
  - [x] 1.6 Update `certs/gen_certs.sh` to generate only CA and server certificates, removing the per-device client cert loop
    - _Requirements: 1.6_

- [x] 2. Auth DB schema migrations (sessions and webhooks tables)
  - [x] 2.1 Add `sessions` and `webhooks` table creation to `init_db()` in the control-center `auth.py`; ensure idempotent migration
    - _Requirements: 3.1, 8.1_
  - [ ]* 2.2 Write migration tests
    - Verify `init_db()` creates both tables on a fresh DB and is idempotent on re-run
    - _Requirements: 3.1, 8.1_

- [x] 3. Token management — backend
  - [x] 3.1 Add `GET /api/tokens` endpoint to control-center that returns all invite tokens with computed `status` field (`pending`/`used`/`expired`)
    - _Requirements: 2.1, 2.2, 2.3, 2.4_
  - [ ]* 3.2 Write property test for token status computation (Property 2)
    - **Property 2: Token status is always correctly computed**
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4**
    - Use Hypothesis: `@given(used_by=st.one_of(st.none(), st.text(min_size=1)), expires_at=st.datetimes())`
  - [x] 3.3 Add `DELETE /api/tokens/{token}` endpoint; reject deletion of `used` or `expired` tokens with HTTP 400
    - _Requirements: 2.7, 2.9_

- [x] 4. Session management — backend
  - [x] 4.1 Update login handler to insert a row into `sessions` table on successful login (jti, username, display_name, login_time, last_seen, user_agent, expires_at)
    - _Requirements: 3.2_
  - [x] 4.2 Add `last_seen` update middleware with 60-second throttle per jti
    - _Requirements: 3.3_
  - [x] 4.3 Update logout and JWT revocation to delete the corresponding `sessions` row and add jti to in-memory blocklist
    - _Requirements: 3.4_
  - [x] 4.4 Add `GET /api/sessions` and `DELETE /api/sessions/{jti}` endpoints (admin only)
    - _Requirements: 3.5, 3.6_
  - [ ]* 4.5 Write property tests for session round-trip and revocation (Properties 3 and 4)
    - **Property 3: Session insert round-trip** — Validates: Requirements 3.2, 3.5
    - **Property 4: Session revocation removes from active list** — Validates: Requirements 3.4, 3.6

- [x] 5. Checkpoint — Ensure all backend auth/session tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Detection persistence — aggregation service
  - [x] 6.1 Create `main/aggregation/detections_db.py` with aiosqlite wrapper; auto-create `detections.db` with the `detections` table and index on startup
    - _Requirements: 5.1_
  - [x] 6.2 Update the aggregation service MQTT tracking payload handler to insert each detection into `detections.db`
    - _Requirements: 5.2_
  - [ ]* 6.3 Write property test for detection persistence round-trip (Property 6)
    - **Property 6: Detection persistence round-trip**
    - **Validates: Requirements 5.1, 5.2**
    - Use Hypothesis: `@given(detections=st.lists(detection_strategy(), min_size=0, max_size=20))`
  - [x] 6.4 Add `GET /devices/{device_id}/detections/export` endpoint to aggregation service with `from`, `to`, and `format=csv` query params; return empty CSV with header when no rows match
    - _Requirements: 5.3, 5.4, 5.5_
  - [ ]* 6.5 Write property test for export time range filter (Property 7)
    - **Property 7: Export time range filter**
    - **Validates: Requirements 5.3, 5.4, 5.5**
    - Use Hypothesis: `@given(detections=st.lists(...), from_ts=st.datetimes(), to_ts=st.datetimes())`
  - [x] 6.6 Proxy `GET /api/devices/{device_id}/detections/export` through control-center (JWT required)
    - _Requirements: 5.3_

- [x] 7. Per-device alert thresholds
  - [x] 7.1 Create `main/aggregation/thresholds.py` with `DeviceThreshold` dataclass; load/save to `/app/data/thresholds.json` for persistence across restarts
    - _Requirements: 6.1_
  - [x] 7.2 Update aggregation service tracking payload handler to evaluate each detection against the device's threshold config before emitting a WebSocket alert; implement `consecutive_frames` counter per device/track
    - _Requirements: 6.2, 6.3, 6.4, 6.5_
  - [ ]* 7.3 Write property test for alert threshold filtering (Property 8)
    - **Property 8: Alert threshold filtering**
    - **Validates: Requirements 6.2, 6.3, 6.4**
    - Use Hypothesis: `@given(confidence=st.floats(0.0, 1.0), label=st.sampled_from([...]), min_confidence=st.floats(0.0, 1.0), alert_classes=st.lists(st.text()))`
  - [x] 7.4 Add `GET /devices/{device_id}/thresholds` and `PUT /devices/{device_id}/thresholds` endpoints to aggregation service
    - _Requirements: 6.6_
  - [x] 7.5 Proxy threshold endpoints through control-center (admin only)
    - _Requirements: 6.6_

- [x] 8. Multi-device PTZ follow
  - [x] 8.1 Create `main/aggregation/ptz_follow.py` with bearing computation function; use camera FOV config (default 60°) and leader compass bearing from sensor payload
    - _Requirements: 7.2, 7.4_
  - [x] 8.2 Write property test for PTZ bearing range (Property 9)
    - **Property 9: PTZ bearing is always in [0, 360)**
    - **Validates: Requirements 7.2, 7.4**
    - Use Hypothesis: `@given(lat=st.floats(-90, 90), lon=st.floats(-180, 180), compass=st.floats(0, 360), cx=st.floats(0, 1))`
  - [x] 8.3 Update aggregation service tracking payload handler to publish `pan_to_bearing` PTZ commands to `uav/ptz/{follower_device_id}` for all configured followers when leader detection arrives
    - _Requirements: 7.3, 7.4_
  - [x] 8.4 Update `edge/config.py` to expose `ptz.follow_leader` field; include it in the edge status payload
    - _Requirements: 7.1, 7.7_
  - [x] 8.5 Add `pan_to_bearing` command handler in `edge/command_handler.py` that delegates to `PTZController`
    - _Requirements: 7.5_
  - [x] 8.6 Create `edge/edge_sim.py` that simulates a second edge device publishing health and tracking payloads over MQTT for PTZ follow testing
    - _Requirements: 7.6_

- [x] 9. Notification webhooks
  - [x] 9.1 Create `main/aggregation/webhook_dispatcher.py` with async fire-and-forget delivery using `httpx.AsyncClient` (5s timeout); include HMAC-SHA256 `X-UAV-Signature` header when secret is non-empty
    - _Requirements: 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_
  - [x] 9.2 Write property test for webhook HMAC signature (Property 10)
    - **Property 10: Webhook HMAC signature is verifiable**
    - **Validates: Requirements 8.6**
    - Use Hypothesis: `@given(body=st.binary(), secret=st.text(min_size=1))`
  - [x] 9.3 Wire webhook dispatcher into aggregation service: call on `detection_alert`, `device_online`, and `device_offline` events; load webhook list from `auth.db` via control-center API or shared config
    - _Requirements: 8.2, 8.3, 8.4_
  - [x] 9.4 Add `GET /api/webhooks`, `POST /api/webhooks`, `PUT /api/webhooks/{id}`, `DELETE /api/webhooks/{id}`, and `POST /api/webhooks/{id}/test` endpoints to control-center (admin only)
    - _Requirements: 8.10, 8.9_

- [x] 10. Edge device offline detection (health timeout)
  - [x] 10.1 Add `last_health_ts` field to `DeviceState` in aggregation service; update it on every received health message
    - _Requirements: 9.1_
  - [x] 10.2 Create `main/aggregation/health_checker.py` background task (runs every 10s via `asyncio`); transition `online` devices to `health_timeout` when `last_health_ts` is >60s old; emit `device_offline` webhook event on transition; restore to `online` when a new health message arrives
    - _Requirements: 9.2, 9.3, 9.4, 9.7_
  - [ ]* 10.3 Write property test for health timeout transitions (Property 11)
    - **Property 11: Health timeout transitions correctly**
    - **Validates: Requirements 9.1, 9.2, 9.7**
    - Use Hypothesis: `@given(elapsed_s=st.floats(min_value=0, max_value=300))`
  - [x] 10.4 Update `DeviceRegistry` to distinguish `offline`, `health_timeout`, and `online` statuses; ensure LWT-based `offline` devices are excluded from health timeout checks
    - _Requirements: 9.5_

- [x] 11. Checkpoint — Ensure all aggregation service and edge tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. Edge device config push
  - [x] 12.1 Add `update_config` action handler in `edge/command_handler.py`; apply `camera_source` and `fps` changes to `CameraSource`, hot-swap `active_model` via `ModelManager.hot_swap()`; silently ignore unrecognized fields
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_
  - [ ]* 12.2 Write property test for update_config field application (Property 5)
    - **Property 5: update_config applies exactly the provided fields**
    - **Validates: Requirements 4.1, 4.2, 4.5**

- [x] 13. IP Webcam remote control — edge
  - [x] 13.1 Create `edge/ipwebcam_handler.py` with `IPWebcamHandler` class; implement `fetch_capabilities()`, `handle_control()`, `fetch_snapshot()`, and `fetch_sensors()` using `urllib.request`; cache capabilities for 5 minutes
    - _Requirements: 14.2, 14.4, 14.5, 14.6, 14.27, 14.28, 14.32_
  - [x] 13.2 Implement all supported settings URL construction in `handle_control()` (zoom, focus, torch, ffc, night_vision, overlay, exposure_lock, whitebalance_lock, video_recording, quality, video_size, manual_sensor, iso, exposure_time, frame_duration, aperture, crop_x, crop_y, focus_mode)
    - _Requirements: 14.7–14.26_
  - [ ]* 13.3 Write property test for IP Webcam URL construction (Property 13)
    - **Property 13: IP Webcam control URL construction**
    - **Validates: Requirements 14.7–14.26**
    - Use Hypothesis: `@given(setting=st.sampled_from(SUPPORTED_SETTINGS), value=st.one_of(st.none(), st.text()))`
  - [x] 13.4 Add `ipwebcam_control` and `ipwebcam_sensors` action handlers in `edge/command_handler.py`; publish capabilities to `uav/ipwebcam/capabilities/{device_id}` on startup; publish snapshot to `uav/snapshot/{device_id}`
    - _Requirements: 14.2, 14.4, 14.5, 14.27, 14.28, 14.31, 14.32_
  - [x] 13.5 Update `edge/config.py` to expose `ipwebcam.url` field; log warning and return error response when `ipwebcam_control` is received but `ipwebcam.url` is not configured
    - _Requirements: 14.1, 14.6_

- [x] 14. IP Webcam remote control — aggregation service
  - [x] 14.1 Subscribe to `uav/ipwebcam/capabilities/{device_id}` and `uav/ipwebcam/sensors/{device_id}` and `uav/snapshot/{device_id}` topics; store capabilities and sensors in `DeviceState`; forward snapshot to frontend via WebSocket
    - _Requirements: 14.3, 14.29, 14.33_
  - [x] 14.2 Add periodic (every 30s) `ipwebcam_sensors` MQTT command publisher in aggregation service
    - _Requirements: 14.31_

- [x] 15. WebRTC black screen fix
  - [x] 15.1 Update `edge/webrtc_streamer.py`: make `CameraVideoTrack._get_frame()` loop with 50ms sleep checking `_stop_event` instead of returning zeros on timeout; store last successful frame and return it when queue is empty; delay `addTrack` until first frame is in queue
    - _Requirements: 13.3, 13.4, 13.5_
  - [ ]* 15.2 Write unit tests for `webrtc_streamer.py`
    - Verify `_get_frame()` returns last frame when queue is empty; verify track is not added before first frame
    - _Requirements: 13.3, 13.4, 13.5_

- [ ] 16. Checkpoint — Ensure all edge and aggregation tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 17. Frontend — bounding box color scheme
  - [x] 17.1 Update `getClassColor` utility in the frontend to accept a `confidence` parameter; implement drone confidence split (`#ef4444` for ≥0.5, `#f97316` for <0.5) and bird color (`#22c55e`); update CSS variable `--uav-class-bird`
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.6_
  - [ ]* 17.2 Write property test for bounding box color rules (Property 12)
    - **Property 12: Bounding box color follows confidence rules**
    - **Validates: Requirements 12.1, 12.2, 12.3**
    - Use fast-check: `fc.property(fc.float({ min: 0, max: 1 }), (confidence) => { ... })`
  - [x] 17.3 Update `TrackingOverlay` to pass `confidence` to `getClassColor`; update overlay legend to show green/red/orange entries
    - _Requirements: 12.1, 12.2, 12.3, 12.5_

- [x] 18. Frontend — WebRTC hook fix
  - [x] 18.1 Update `useWebRTCStream` hook: call `videoRef.current.play()` in `ontrack` with autoplay error catch; transition `streamState` to `"connected"` only on `canplay`/`loadedmetadata` event
    - _Requirements: 13.1, 13.2_
  - [x] 18.2 Add `onCanPlay` handler to `<video>` element in `FeedCell` that calls `.play()`
    - _Requirements: 13.6_

- [x] 19. Frontend — Settings page: Tokens tab
  - [x] 19.1 Add "Tokens" tab to Settings page (admin only); render table with columns Token, Role, Created By, Created At, Expires At, Status, Used By; wire "Revoke" button to `DELETE /api/tokens/{token}` and remove row on success; wire "Copy Link" button to copy `/register?token=<value>` to clipboard
    - _Requirements: 2.5, 2.6, 2.7, 2.8_

- [x] 20. Frontend — Settings page: Sessions tab
  - [x] 20.1 Add "Sessions" tab to Settings page (admin only); render table with columns Username, Display Name, Login Time, Last Seen, User Agent, Revoke; wire "Revoke" button to `DELETE /api/sessions/{jti}` and remove row on success
    - _Requirements: 3.7, 3.8, 3.9_

- [x] 21. Frontend — Settings page: Notifications (webhooks) tab
  - [x] 21.1 Add "Notifications" tab to Settings page (admin only); render existing webhooks table with enable/disable toggle, test, and delete actions; add form to create new webhook (URL, events checkboxes, secret); wire all actions to the corresponding `/api/webhooks` endpoints
    - _Requirements: 8.8, 8.9, 8.10_

- [x] 22. Frontend — Settings page: per-device threshold editor
  - [x] 22.1 Add per-device threshold editor to Settings page accessible from the device list; include fields for `min_confidence`, `consecutive_frames`, and `alert_classes`; wire save to `PUT /api/devices/{device_id}/thresholds`
    - _Requirements: 6.7, 6.8_

- [x] 23. Frontend — Device Detail page additions
  - [x] 23.1 Add "Edit Config" panel to Device Detail page with fields for `camera_source`, `fps`, and `active_model`; POST to `/api/command/{device_id}` with `action: "update_config"` on submit
    - _Requirements: 4.6, 4.7, 4.8_
  - [x] 23.2 Add "IP Webcam Controls" panel to Device Detail page (visible only when `ipwebcam_capabilities` is present in device state); organise into Stream, Camera, Focus, Exposure, and Recording sections; populate dropdowns and sliders from capabilities payload; send `ipwebcam_control` command on change; convert exposure/frame duration between ms (UI) and ns (command)
    - _Requirements: 14.35, 14.36, 14.37, 14.38, 14.39, 14.40_
  - [x] 23.3 Disable ISO, exposure_time, frame_duration, and aperture controls when `manual_sensor` is off; display them as read-only
    - _Requirements: 14.23_
  - [x] 23.4 Add snapshot modal to Device Detail page: "Snapshot" button sends `ipwebcam_control` with `setting: "snapshot"`; display received base64 image in modal with download button
    - _Requirements: 14.30_
  - [x] 23.5 Add IP Webcam sensor data display (battery_level, battery_temp, light, motion, pressure, audio_connections) to the health section when sensor data is available in device state
    - _Requirements: 14.34_

- [x] 24. Frontend — Logs page: detection export
  - [x] 24.1 Add "Export Detections" button to Logs page; open date range picker with `from`/`to` fields and device selector; trigger file download by navigating to the export endpoint URL with selected parameters
    - _Requirements: 5.6, 5.7_

- [x] 25. Frontend — Dashboard: health timeout indicator
  - [x] 25.1 Update Dashboard device status indicators to show amber/yellow for `health_timeout` devices, distinct from the red `offline` indicator
    - _Requirements: 9.6_

- [x] 26. Checkpoint — Ensure all frontend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 27. Launcher redesign
  - [x] 27.1 Refactor `launcher_main.py` to use `ttk.Notebook` with Config, Status, and Logs tabs; apply dark color scheme (`#0f172a` background, `#1e293b` card, `#3b82f6` accent); retain all existing functionality
    - _Requirements: 10.1, 10.9, 10.10_
  - [x] 27.2 Add Status tab to Main Launcher: poll `docker compose ps` every 5s in a daemon thread; display green/red dot per service; update via `widget.after(0, ...)`
    - _Requirements: 10.3_
  - [x] 27.3 Add Logs tab to Main Launcher: tail `docker compose logs -f` in a background thread; append lines to scrolling text area with auto-scroll
    - _Requirements: 10.5_
  - [x] 27.4 Add per-service start/stop controls to Main Launcher Config tab
    - _Requirements: 10.6_
  - [x] 27.5 Refactor `launcher_edge.py` to use `ttk.Notebook` with Config, Status, and Logs tabs; replace CA cert, client cert, and client key fields with a single password field; apply same dark color scheme
    - _Requirements: 10.2, 10.9, 1.9_
  - [x] 27.6 Add Status tab to Edge Launcher: display inference process status and last-seen MQTT connection state
    - _Requirements: 10.4_
  - [x] 27.7 Add Logs tab to Edge Launcher: tail subprocess stdout in a background thread; append to scrolling text area with auto-scroll
    - _Requirements: 10.5_
  - [x] 27.8 Add "Test Connection" button to Edge Launcher Config tab that verifies MQTT connectivity using configured username and password
    - _Requirements: 10.7_
  - [x] 27.9 Add camera preview thumbnail to Edge Launcher Config tab that captures and displays a single frame from the configured camera source
    - _Requirements: 10.8_

- [x] 28. Electron desktop app
  - [x] 28.1 Create `electron/` directory with `package.json`, `electron-builder.yml`, and `main.js`; implement main process: spawn `docker compose up -d`, poll `http://localhost:8080` every 2s until HTTP 200 or 401, then show `BrowserWindow` loading `http://localhost:8080`
    - _Requirements: 11.1, 11.2, 11.3_
  - [x] 28.2 Add loading screen displayed while Docker stack is starting; show error dialog with "Retry" button if compose fails or times out after 60s
    - _Requirements: 11.9_
  - [x] 28.3 Implement system tray icon with "Open", "Stop Stack", and "Quit" menu items; wire "Stop Stack" to `docker compose down`; wire "Quit" to `docker compose down` then `app.quit()`
    - _Requirements: 11.4, 11.5, 11.6_
  - [x] 28.4 Create `electron/preload.js` (minimal context bridge); create `electron/PKGBUILD` for Arch Linux installation; configure `electron-builder.yml` for AppImage output
    - _Requirements: 11.7, 11.8_

- [x] 29. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests use Hypothesis (Python) and fast-check (TypeScript) with a minimum of 100 iterations each
- All shell scripts must use `bash` explicitly (e.g., `bash script.sh`) — fish is the default shell on this machine
- The project already has a working v2; these are incremental changes, not a rewrite
