# Implementation Plan: Anti-UAV Detection System

## Overview

Incremental implementation starting with shared schemas and infrastructure, then edge device, main device services, frontend, and optional components. Each task builds on the previous and ends with integration. Property-based tests use `hypothesis` and are placed close to the code they validate.

## Tasks

- [x] 1. Project structure and shared schemas
  - Create directory layout: `edge/`, `main/aggregation/`, `main/control-center/`, `main/signaling/`, `frontend/`, `shared/schemas/`, `certs/`, `secrets/`, `docker/`
  - Write `shared/schemas/tracking_payload.schema.json` (JSON Schema Draft-07) with all required and optional fields from the data model
  - Write `shared/schemas/status_payload.schema.json`, `ptz_command.schema.json`, `ptz_status.schema.json`, `command_payload.schema.json`, `sensor_payload.schema.json`
  - Add `.gitignore` entries for `secrets/`, `.env`, `*.key`, `*.crt`, `__pycache__/`, `node_modules/`, `dist/`
  - _Requirements: 9.1, 2.2, 10.1_

- [x] 2. TLS certificate generation scripts
  - Write `certs/gen_certs.sh`: generates a self-signed CA, server cert for the broker, and per-device client certs using `openssl`
  - Script accepts `DEVICE_IDS` env var (space-separated list) and outputs all certs/keys to `secrets/`
  - Write `certs/README.md` documenting usage
  - _Requirements: 11.1, 11.3, 11.4, 3.1_

- [x] 3. Mosquitto MQTT broker configuration
  - Write `docker/mosquitto/mosquitto.conf` template supporting TLS on port 8883, `require_certificate true`, and optional `password_file` fallback
  - Write `docker/mosquitto/Dockerfile` (FROM eclipse-mosquitto:2) that copies the config template
  - Write `docker/mosquitto/entrypoint.sh` that substitutes env vars into the config at container start
  - _Requirements: 3.1, 3.2, 3.3, 3.5, 11.1, 11.3_

- [x] 4. Docker Compose stack (main device)
  - Write `docker/docker-compose.yml` defining services: `mosquitto`, `aggregation`, `control-center`, `signaling`, `tile-server`, `nginx` (optional non-VPN mode)
  - Set `depends_on` ordering: mosquitto → aggregation, control-center; aggregation → control-center
  - Set `restart: unless-stopped` on all services
  - Mount `secrets/` as read-only volumes into mosquitto and aggregation
  - Write `docker/.env.example` with all variables from the design (`MQTT_PORT`, `MQTT_TLS_*`, `AGGREGATION_PORT`, `CONTROL_CENTER_PORT`, `SIGNALING_PORT`, `REMOTE_ACCESS_MODE`, `HTTPS_TOKEN`, `RADAR_ENABLED`, `TILE_SERVER_URL`)
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 10.2_

- [x] 5. Edge device — configuration loader
  - Write `edge/config.py`: loads `config.yaml` (path from `EDGE_CONFIG` env var or default `./config.yaml`) using PyYAML; validates required fields (`device_id`, `mqtt.host`, `mqtt.port`, `camera.source`, `active_model`); exits with code 1 and logs missing field name on validation failure
  - Write `edge/config.example.yaml` matching the design's Device Configuration File schema
  - _Requirements: 10.1, 10.3, 1.4_

  - [ ]* 5.1 Write unit tests for config loader
    - Test missing required field exits with code 1 and logs field name
    - Test valid config loads without error
    - Test env var override of config path
    - _Requirements: 10.3_

- [x] 6. Edge device — inference engine
  - Write `edge/inference_engine.py`: loads YOLO26 `.pt` model via `ultralytics.YOLO`; processes frames from a `queue.Queue` at configurable target FPS; applies CLAHE + colormap normalization when `camera_mode == "thermal"`; runs ByteTrack tracker; produces `Tracking_Payload` dicts
  - Implement `ModelManager` class: registry of named model profiles from config; `hot_swap(model_name)` loads new model in background thread and swaps atomically; publishes current model name in status
  - Exit with code 1 and log error if PT_Model file not found at startup
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 18.1, 18.4, 18.5, 18.10_

  - [ ]* 6.1 Write property test for thermal preprocessing (Property 12)
    - **Property 12: Thermal Preprocessing Changes Frame Data**
    - **Validates: Requirements 18.10**
    - Generate random numpy arrays; apply thermal preprocessing; assert output != input

  - [ ]* 6.2 Write property test for model profile structure (Property 10)
    - **Property 10: Model Profile Structure is Valid**
    - **Validates: Requirements 18.1**
    - Generate random model profile dicts; assert required fields and valid `camera_mode`

  - [ ]* 6.3 Write property test for status includes active model (Property 11)
    - **Property 11: Status Message Includes Active Model Name**
    - **Validates: Requirements 18.7**
    - Generate random model profile names; simulate status publish; assert `active_model` field matches

  - [ ]* 6.4 Write unit tests for inference engine
    - Test missing model file exits with code 1
    - Test thermal preprocessing is applied when `camera_mode == "thermal"` and skipped otherwise
    - Test hot-swap resumes publishing after model load
    - _Requirements: 1.4, 18.4, 18.5, 18.10_

- [x] 7. Edge device — camera source and frame queue
  - Write `edge/camera.py`: opens camera source (USB `/dev/videoN`, RTSP URL, MJPEG HTTP URL) via `cv2.VideoCapture`; pushes frames into a `queue.Queue` at target FPS; on disconnection logs error, retries every 5 seconds, resumes on reconnect
  - _Requirements: 1.2, 1.5_

  - [ ]* 7.1 Write unit tests for camera reconnect logic
    - Test that disconnection triggers retry loop at 5-second intervals
    - Test that inference resumes after reconnect
    - _Requirements: 1.5_

- [x] 8. Edge device — Tracking_Payload serialization
  - Write `edge/payload.py`: `build_tracking_payload(device_id, frame_id, results, active_model, sensor_data=None)` → dict; `serialize(payload)` → UTF-8 JSON bytes; `deserialize(data)` → dict
  - Ensure payload conforms to `tracking_payload.schema.json`; include optional fields only when enabled
  - _Requirements: 1.3, 2.1, 2.2, 9.1, 9.3_

  - [ ]* 8.1 Write property test for round-trip serialization (Property 1)
    - **Property 1: Tracking Payload Round-Trip Serialization**
    - **Validates: Requirements 9.3**
    - Generate random valid `Tracking_Payload` dicts; serialize → deserialize; assert structural equality

- [x] 9. Edge device — MQTT client
  - Write `edge/mqtt_client.py`: connects to broker with TLS (cert-based or user/pass from config); publishes `uav/tracking/{device_id}` (QoS 0) within 100ms of payload build; publishes retained `uav/status/{device_id}` on connect; sets LWT `offline` status; subscribes to `uav/command/{device_id}` (QoS 1) and `uav/ptz/{device_id}` (QoS 0); implements exponential backoff reconnect (1s, 2s, 4s … max 60s)
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 11.1, 11.3_

  - [ ]* 9.1 Write unit tests for MQTT client
    - Test exponential backoff sequence caps at 60s
    - Test LWT message is set correctly on connect
    - Test TLS connection parameters are passed from config
    - _Requirements: 2.3, 2.4, 2.5_

- [x] 10. Edge device — command handler
  - Write `edge/command_handler.py`: dispatches `start_stream` / `stop_stream` commands to the WebRTC streamer; dispatches `switch_model` to `ModelManager`; handles missing model file (log error, retain current model, publish error status); handles `stop_stream` within 2s and `start_stream` within 3s
  - _Requirements: 7.3, 7.4, 18.3, 18.4, 18.6_

  - [ ]* 10.1 Write property test for control command topic (Property 5)
    - **Property 5: Control Command Published to Correct Topic**
    - **Validates: Requirements 7.1, 7.2**
    - Generate random device IDs and actions; assert topic is `uav/command/{device_id}` and action is `start_stream` or `stop_stream`

  - [ ]* 10.2 Write unit tests for command handler
    - Test `stop_stream` suspends publishing within 2s
    - Test `start_stream` resumes publishing within 3s
    - Test `switch_model` with missing file retains current model and publishes error status
    - _Requirements: 7.3, 7.4, 18.6_

- [x] 11. Edge device — PTZ controller
  - Write `edge/ptz_controller.py`: dispatches PTZ commands to the correct driver based on `ptz.hardware_type` in config (`visca_serial`, `visca_ip`, `onvif`, `arduino`, `digital`); implements all 10 command types from Requirement 13.3; publishes PTZ status to `uav/ptz/status/{device_id}` after each command; silently ignores commands when PTZ is disabled; logs error and disables PTZ for session if serial port unavailable
  - Implement `DigitalZoomDriver`: applies software crop/zoom to frames
  - Implement `ViscaSerialDriver` and `ViscaIpDriver` with the VISCA binary protocol
  - Implement `OnvifDriver` using `onvif-zeep`
  - _Requirements: 13.2, 13.3, 13.4, 13.5, 13.6, 13.7, 13.8_

  - [ ]* 11.1 Write property test for PTZ command topic and structure (Property 4)
    - **Property 4: PTZ Command Published to Correct Topic with Valid Structure**
    - **Validates: Requirements 13.2, 13.3**
    - Generate random device IDs and PTZ command types; assert topic is `uav/ptz/{device_id}` and command is in the valid set

  - [ ]* 11.2 Write unit tests for PTZ controller
    - Test all 10 command types are dispatched without error
    - Test PTZ disabled silently ignores commands (no log)
    - Test serial port unavailable disables PTZ and continues inference
    - _Requirements: 13.3, 13.6, 13.8_

- [x] 12. Edge device — WebRTC streamer
  - Write `edge/webrtc_streamer.py`: uses `aiortc` to create a `RTCPeerConnection`; implements `VideoStreamTrack` that reads frames from the camera queue; connects to the signaling server WebSocket; handles `register`, `request_offer`, `answer`, and `ice_candidate` signaling messages; starts/stops on command; DTLS-SRTP enforced by aiortc
  - _Requirements: 5.1, 7.3, 7.4, 11.2_

- [x] 13. Edge device — sensor reader (optional)
  - Write `edge/sensor_reader.py`: reads compass bearing and pitch from a configurable source (serial NMEA or HTTP endpoint from IP Webcam app); publishes `uav/sensor/{device_id}` (QoS 0) as `Sensor_Payload` JSON; validates bearing in [0, 360) and pitch in [-90, 90] before publishing
  - _Requirements: 17.3, 17.4_

  - [ ]* 13.1 Write property test for sensor payload ranges (Property 9)
    - **Property 9: Sensor Payload Fields are Within Valid Ranges**
    - **Validates: Requirements 17.3**
    - Generate random sensor payloads; assert `compass_bearing_deg` in [0, 360) and `pitch_deg` in [-90, 90]

- [x] 14. Edge device — distance and trajectory estimator (optional)
  - Write `edge/estimator.py`: implements `estimate_distance(bbox_width_px, frame_width_px, fov_deg, reference_size_m)` using the pinhole camera formula; implements `estimate_trajectory(centroid_history, window_frames)` as mean of frame-to-frame displacements; attaches results to payload as `estimated_distance_m` and `trajectory_vector` when enabled
  - _Requirements: 17.1, 17.2, 17.5, 17.7_

  - [ ]* 14.1 Write property test for distance estimation monotonicity (Property 7)
    - **Property 7: Distance Estimation is Positive and Monotonically Decreasing with Bbox Size**
    - **Validates: Requirements 17.1**
    - Generate pairs `(w1, w2)` where `w1 > w2 > 0`; assert `distance(w1) < distance(w2)` and both are positive

  - [ ]* 14.2 Write property test for trajectory vector correctness (Property 8)
    - **Property 8: Trajectory Vector Reflects Direction of Motion**
    - **Validates: Requirements 17.2**
    - Generate random sequences of N centroids; assert computed `(dx, dy)` equals mean of frame-to-frame displacements

- [x] 15. Edge device — main entry point and wiring
  - Write `edge/main.py`: loads config; starts camera thread, inference engine, MQTT client, command handler, and optionally sensor reader and estimator; wires all components together; handles graceful shutdown on SIGTERM/SIGINT
  - Write `edge/requirements.txt`: `ultralytics`, `paho-mqtt`, `aiortc`, `PyYAML`, `opencv-python`, `onvif-zeep`, `hypothesis`, `pytest`
  - Write `edge/Dockerfile`: FROM python:3.11-slim; installs requirements; copies source; sets entrypoint to `python main.py`
  - _Requirements: 1.1, 1.2, 2.3, 10.1, 10.3_

- [ ] 16. Checkpoint — edge device tests pass
  - Ensure all edge device unit and property tests pass: `pytest edge/tests/ --hypothesis-seed=0`
  - Ask the user if questions arise before proceeding.

- [x] 17. Aggregation service — JSON schema validator
  - Write `main/aggregation/validator.py`: loads `tracking_payload.schema.json` using `jsonschema`; exposes `validate_payload(data) -> bool`; logs malformed message with `device_id` and returns `False` on failure; rejects `confidence` outside [0.0, 1.0]
  - _Requirements: 4.4, 9.2, 9.4_

  - [ ]* 17.1 Write property test for schema validation rejects invalid payloads (Property 2)
    - **Property 2: Tracking Payload Schema Validation Rejects Invalid Payloads**
    - **Validates: Requirements 9.1, 9.2, 9.4**
    - Generate payloads with one field mutated to be invalid; assert validator rejects each

- [x] 18. Aggregation service — device state registry
  - Write `main/aggregation/registry.py`: `DeviceRegistry` class with `Dict[device_id, DeviceState]`; `update_tracking(payload)`, `update_status(device_id, status)`, `update_ptz_status(payload)`, `update_sensor(payload)` methods; thread-safe with `asyncio.Lock`
  - _Requirements: 4.2, 4.3, 6.5_

  - [ ]* 18.1 Write property test for device registry reflects status messages (Property 3)
    - **Property 3: Device Registry Reflects Status Messages**
    - **Validates: Requirements 4.3**
    - Generate random sequences of online/offline status messages per device ID; assert registry reflects the last message per device

- [x] 19. Aggregation service — MQTT subscriber
  - Write `main/aggregation/mqtt_subscriber.py`: uses `asyncio-mqtt` to subscribe to `uav/tracking/#`, `uav/status/#`, `uav/ptz/status/#`, `uav/sensor/#`, and optionally `uav/radar/#`; validates tracking payloads via `validator.py`; updates `DeviceRegistry`; reconnects with backoff on broker disconnect
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 14.1_

- [x] 20. Aggregation service — WebSocket push and REST API
  - Write `main/aggregation/app.py`: FastAPI app with `/ws` WebSocket endpoint that pushes `DeviceRegistry` state updates to all connected frontend clients; REST endpoints: `GET /devices`, `GET /devices/{device_id}`, `POST /command/{device_id}`, `POST /ptz/{device_id}`; publishes commands to MQTT on behalf of frontend
  - _Requirements: 4.2, 7.1, 7.2, 13.2_

  - [ ]* 20.1 Write unit tests for aggregation REST API
    - Test `POST /command/{device_id}` publishes correct MQTT message
    - Test `POST /ptz/{device_id}` publishes to correct topic
    - Test WebSocket push delivers state update to connected client
    - _Requirements: 4.2, 7.1, 7.2, 13.2_

- [x] 21. Aggregation service — radar normalization (optional)
  - Write `main/aggregation/radar_normalizer.py`: `normalize_radar_track(raw_track) -> dict` maps radar fields to `Tracking_Payload` schema with `source: "radar"` and `label: "radar"`; validates output against schema; logs warning every 60s if radar source unreachable
  - _Requirements: 14.1, 14.2, 14.4, 14.5_

  - [ ]* 21.1 Write property test for radar track normalization (Property 6)
    - **Property 6: Radar Track Normalization Preserves Required Fields**
    - **Validates: Requirements 14.2**
    - Generate random radar track dicts; normalize; assert `source == "radar"`, `label == "radar"`, and schema valid

- [x] 22. Aggregation service — Dockerfile and wiring
  - Write `main/aggregation/requirements.txt`: `fastapi`, `uvicorn`, `asyncio-mqtt`, `jsonschema`, `pydantic`, `hypothesis`, `pytest`, `httpx`
  - Write `main/aggregation/Dockerfile`: FROM python:3.11-slim; installs requirements; copies source; entrypoint `uvicorn app:app`
  - _Requirements: 4.5, 8.1_

- [x] 23. WebRTC signaling server
  - Write `main/signaling/server.js`: Node.js + `ws` WebSocket server; implements room-based signaling: edge devices register as `publisher`, browsers connect as `subscriber`; relays `offer`, `answer`, `ice_candidate` messages between publisher and subscriber for the same `device_id`; handles disconnect cleanup
  - Write `main/signaling/package.json` with `ws` dependency
  - Write `main/signaling/Dockerfile`: FROM node:20-alpine; installs deps; entrypoint `node server.js`
  - _Requirements: 5.1, 5.2, 11.2_

  - [ ]* 23.1 Write unit tests for signaling server
    - Test publisher registration and subscriber pairing
    - Test SDP offer/answer relay between publisher and subscriber
    - Test ICE candidate relay
    - Test disconnect cleanup removes room entry
    - _Requirements: 5.1_

- [x] 24. Control center backend
  - Write `main/control-center/app.py`: FastAPI app; serves React frontend static files from `dist/`; `GET /api/devices` proxies to aggregation service; proxies WebSocket `/ws` to aggregation `/ws`; enforces `Authorization: Bearer <token>` when `REMOTE_ACCESS_MODE=https`; logs startup warning when non-VPN mode is active
  - _Requirements: 6.1, 15.2, 15.3, 15.5_

  - [ ]* 24.1 Write unit tests for control center backend
    - Test token auth rejects requests without valid token in HTTPS mode
    - Test startup warning is logged when `REMOTE_ACCESS_MODE=https`
    - Test static file serving returns 200 for index.html
    - _Requirements: 15.3, 15.5_

- [x] 25. nginx reverse proxy configuration (optional non-VPN mode)
  - Write `docker/nginx/nginx.conf`: HTTPS termination on port 443; `proxy_pass` to control-center on port 8080; `proxy_pass` WebSocket upgrade for `/ws`; `auth_request` or `proxy_set_header Authorization` token enforcement
  - Write `docker/nginx/Dockerfile`: FROM nginx:alpine; copies config
  - _Requirements: 15.2, 15.3, 15.4_

- [ ] 26. Checkpoint — main device services tests pass
  - Ensure all aggregation and control-center unit and property tests pass
  - Verify `docker compose up -d` starts all services in correct order
  - Ask the user if questions arise before proceeding.

- [x] 27. Frontend — project scaffold and types
  - Initialize Vite + React TypeScript project in `frontend/`; install dependencies: `leaflet`, `react-leaflet`, `react-joystick-component`, `@types/leaflet`
  - Write `frontend/src/types/index.ts`: TypeScript interfaces for `TrackingPayload`, `Detection`, `DeviceState`, `PtzCommand`, `CommandPayload`, `SensorData`, `ModelProfile`
  - Write `frontend/src/api/websocket.ts`: WebSocket client that connects to `/ws`, parses incoming `DeviceState` updates, and exposes an event emitter / React context
  - _Requirements: 9.1, 6.1_

- [x] 28. Frontend — device dashboard
  - Write `frontend/src/components/DeviceDashboard.tsx`: table listing all devices with online/offline status badge (green/grey), active model name, detection count, and model selector dropdown; updates within 2s of status change; dispatches `switch_model` command via `POST /command/{device_id}`
  - _Requirements: 6.2, 6.5, 18.7, 18.8, 18.9_

- [x] 29. Frontend — map view
  - Write `frontend/src/components/MapView.tsx`: Leaflet.js map with tile URL from `VITE_TILE_SERVER_URL` env var (self-hosted OSM); renders a marker per device at configured lat/lon; green marker for online, grey for offline; pulsing CSS alert indicator on detection; alert popup shows `device_id`, UTC timestamp, detection count; auto-clears alert after configurable timeout; dismisses on click; renders radar tracks with diamond marker style
  - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7, 12.8, 12.10, 14.3_

  - [ ]* 29.1 Write property test for alert marker fields (Property 13)
    - **Property 13: Alert Marker Displays Required Detection Fields**
    - **Validates: Requirements 12.4**
    - Generate random detection events; build alert marker data structure; assert `device_id`, valid UTC `timestamp`, and non-negative integer `detection_count` are present

- [x] 30. Frontend — live feed grid
  - Write `frontend/src/components/LiveFeedGrid.tsx`: CSS grid of up to 4 `<video>` elements; each video connected to a WebRTC peer connection via the browser's native `RTCPeerConnection` API; connects to signaling server WebSocket to exchange SDP/ICE; displays visual indicator on stream interruption and attempts reconnect; shows PTZ controls overlay when device has PTZ enabled
  - _Requirements: 5.2, 5.3, 5.4, 5.5, 6.3, 6.4_

- [x] 31. Frontend — tracking overlay
  - Write `frontend/src/components/TrackingOverlay.tsx`: `<canvas>` element overlaid on each video feed; draws bounding boxes and track IDs from the latest `TrackingPayload` received via WebSocket; updates at the same rate as incoming payloads; displays `estimated_distance_m` and `trajectory_vector` when present
  - _Requirements: 5.3, 5.4, 17.6_

- [x] 32. Frontend — PTZ controls
  - Write `frontend/src/components/PtzControls.tsx`: joystick component (`react-joystick-component`) for continuous pan/tilt; discrete buttons for zoom in/out, reset home; absolute angle/zoom inputs; publishes PTZ commands via `POST /ptz/{device_id}`; only rendered when device has PTZ enabled
  - _Requirements: 13.1, 13.2, 13.3_

- [x] 33. Frontend — model switcher
  - Write `frontend/src/components/ModelSwitcher.tsx`: per-device dropdown listing model profiles from `GET /api/devices/{device_id}`; on selection dispatches `switch_model` command; displays currently active model name
  - _Requirements: 18.8, 18.9_

- [x] 34. Frontend — command timeout warning
  - Implement 5-second timeout in `frontend/src/api/commands.ts`: after issuing any command, if no acknowledgement status update is received via WebSocket within 5s, display a timeout warning toast/banner to the operator
  - _Requirements: 7.5_

- [x] 35. Frontend — build and static file integration
  - Configure `vite.config.ts` with `VITE_TILE_SERVER_URL`, `VITE_AGGREGATION_WS_URL`, `VITE_SIGNALING_URL` env vars
  - Add `frontend/Dockerfile`: FROM node:20-alpine build stage; `npm run build`; output `dist/` copied into control-center container's static directory
  - Update `docker-compose.yml` to build frontend and mount `dist/` into control-center service
  - _Requirements: 6.1, 8.1_

- [ ] 36. Checkpoint — full stack integration
  - Ensure all unit and property tests pass across edge, aggregation, and frontend
  - Verify end-to-end flow: edge device publishes payload → aggregation validates and pushes via WebSocket → frontend renders bounding box overlay and map alert
  - Ask the user if questions arise before proceeding.

- [x] 37. Arduino controller integration (optional)
  - Write `edge/ptz_drivers/arduino_driver.py`: opens serial connection to Arduino at startup; translates PTZ commands to `PAN:<angle>\n`, `TILT:<angle>\n`, `ZOOM:<level>\n`, `HOME\n` serial protocol; logs error and disables PTZ if serial port unavailable
  - Update `edge/ptz_controller.py` to dispatch to `ArduinoDriver` when `hardware_type == "arduino"`
  - _Requirements: 16.1, 16.2, 16.3, 16.5_

- [x] 38. WireGuard VPN configuration
  - Write `docker/wireguard/wg0.conf.example`: WireGuard server config template with `[Interface]` and `[Peer]` sections; document how to generate key pairs and add operator peers
  - Write `docker/wireguard/README.md`: setup instructions for adding the WireGuard container or host service to the stack
  - _Requirements: 15.1, 15.4_

- [x] 39. pytest configuration and hypothesis profiles
  - Write `edge/tests/conftest.py` and `main/aggregation/tests/conftest.py`: register hypothesis `ci` profile with `max_examples=100` and `suppress_health_check=[HealthCheck.too_slow]`; add `--hypothesis-seed=0` to `pytest.ini` / `pyproject.toml`
  - Ensure all 13 property tests are tagged with `# Feature: anti-uav-detection-system, Property N: <title>` comments
  - _Requirements: (all correctness properties)_

- [x] 40. Final checkpoint — all tests pass
  - Run `pytest edge/tests/ main/aggregation/tests/ --hypothesis-seed=0 -v` and confirm all unit and property tests pass
  - Ask the user if questions arise before proceeding.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Property tests (P1–P13) are placed close to the implementation they validate to catch errors early
- Checkpoints at tasks 16, 26, 36, and 40 ensure incremental validation before moving to the next layer
- The `secrets/` directory is never committed; run `certs/gen_certs.sh` before first deployment
