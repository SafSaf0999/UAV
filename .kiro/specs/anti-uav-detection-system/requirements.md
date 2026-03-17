# Requirements Document

## Introduction

An anti-UAV detection system that runs YOLO v26 (Ultralytics) inference on distributed edge devices to detect and track unmanned aerial vehicles (UAVs). Edge devices stream tracking data to a central main device via MQTT (with TLS encryption and authentication). Live video is streamed from edge devices to the control center using WebRTC. The main device runs Docker to host an MQTT broker, a data aggregation service, and a control center web UI that displays live video feeds and real-time tracking overlays from all connected edge devices. The system supports 5 or more simultaneous edge devices.

> Note: Study papers shared by the user will be incorporated during the design phase to inform architectural and algorithmic decisions.

## Glossary

- **Edge_Device**: A resource-constrained device that runs YOLO v26 inference on a local camera feed and publishes tracking results via MQTT.
- **Main_Device**: The central server running Docker that hosts the MQTT broker, aggregation service, and control center.
- **MQTT_Broker**: The message broker (running in Docker on the Main_Device) that routes messages between Edge_Devices and the Main_Device services.
- **Inference_Engine**: The YOLO v26 (Ultralytics) model runtime on an Edge_Device that processes camera frames and produces detection/tracking output.
- **Aggregation_Service**: A Docker service on the Main_Device that subscribes to MQTT topics and consolidates tracking data from all Edge_Devices.
- **Control_Center**: A locally-hosted web application served from the Main_Device that displays live feeds and tracking data, and allows operators to control edge device streams.
- **Tracking_Payload**: A structured JSON message published by an Edge_Device containing detection bounding boxes, confidence scores, class labels, track IDs, and a timestamp.
- **Live_Feed**: A real-time video stream from an Edge_Device's camera, viewable in the Control_Center.
- **Operator**: A human user interacting with the Control_Center via a web browser on the local network.
- **PT_Model**: The pre-trained YOLO v26 `.pt` weights file loaded by the Inference_Engine.
- **TLS**: Transport Layer Security — the cryptographic protocol used to encrypt MQTT connections and all data in transit between system components.
- **WebRTC**: Web Real-Time Communication — the browser-native protocol used to stream live video from Edge_Devices to the Control_Center with low latency.
- **PTZ_Controller**: The software or hardware component on an Edge_Device responsible for translating PTZ commands into motor control signals or hardware protocol messages (e.g., VISCA, ONVIF, or Arduino motor driver).
- **Radar_Source**: An external radar-based UAV detection system that publishes track data to the Aggregation_Service via a standardized interface.
- **Sensor_Payload**: A structured JSON message published by an Edge_Device containing sensor readings such as GPS coordinates and compass heading, used for UAV bearing and trajectory estimation.

---

## Requirements

### Requirement 1: Edge Device Inference

**User Story:** As an operator, I want each edge device to continuously run UAV detection inference on its camera feed, so that UAVs are identified in real time at the point of capture.

#### Acceptance Criteria

1. THE Inference_Engine SHALL load the PT_Model from a configurable file path at startup.
2. WHEN the Inference_Engine starts, THE Inference_Engine SHALL begin processing camera frames continuously at a configurable target frame rate.
3. WHEN a frame is processed, THE Inference_Engine SHALL produce a Tracking_Payload containing bounding boxes, confidence scores, class labels, track IDs, and a UTC timestamp for each detected object.
4. IF the PT_Model file is not found at the configured path, THEN THE Inference_Engine SHALL log an error message and exit with a non-zero status code.
5. IF the camera feed becomes unavailable, THEN THE Inference_Engine SHALL log the disconnection, attempt reconnection at 5-second intervals, and resume inference upon successful reconnection.

---

### Requirement 2: MQTT Communication from Edge Devices

**User Story:** As a system integrator, I want edge devices to publish tracking results over MQTT, so that the central device can receive and process detections from all cameras.

#### Acceptance Criteria

1. WHEN a Tracking_Payload is produced, THE Edge_Device SHALL publish it to the MQTT topic `uav/tracking/{device_id}` within 100ms of frame processing completion.
2. THE Edge_Device SHALL publish Tracking_Payloads as UTF-8 encoded JSON conforming to the defined Tracking_Payload schema.
3. WHEN the Edge_Device starts, THE Edge_Device SHALL connect to the MQTT_Broker using TLS encryption with a configurable host, port, and TLS credentials (certificate-based or username/password).
4. IF the MQTT_Broker connection is lost, THEN THE Edge_Device SHALL attempt reconnection using exponential backoff with a maximum interval of 60 seconds.
5. THE Edge_Device SHALL publish a retained `uav/status/{device_id}` message with status `online` on connect and `offline` as a Last Will and Testament message.

---

### Requirement 3: MQTT Broker on Main Device

**User Story:** As a system integrator, I want a managed MQTT broker running on the main device, so that all edge devices have a reliable message routing hub.

#### Acceptance Criteria

1. THE MQTT_Broker SHALL run as a Docker container on the Main_Device and accept TLS-encrypted connections on a configurable port (default 8883).
2. THE MQTT_Broker SHALL require client authentication for all connections using either TLS client certificates or username/password credentials.
3. THE MQTT_Broker SHALL support at least 50 simultaneous client connections.
4. IF an Edge_Device disconnects unexpectedly, THEN THE MQTT_Broker SHALL deliver the Last Will and Testament `offline` status message to all subscribers of `uav/status/{device_id}`.
5. THE MQTT_Broker SHALL reject any connection attempt that does not provide valid authentication credentials.

---

### Requirement 4: Data Aggregation Service

**User Story:** As an operator, I want all tracking data from edge devices to be consolidated centrally, so that the control center can display a unified operational picture.

#### Acceptance Criteria

1. THE Aggregation_Service SHALL subscribe to the wildcard MQTT topic `uav/tracking/#` and receive Tracking_Payloads from all Edge_Devices.
2. WHEN a Tracking_Payload is received, THE Aggregation_Service SHALL store the latest tracking state per device_id and make it available to the Control_Center within 200ms.
3. THE Aggregation_Service SHALL subscribe to `uav/status/#` and maintain a registry of connected and disconnected Edge_Devices.
4. IF a Tracking_Payload fails JSON schema validation, THEN THE Aggregation_Service SHALL log the malformed message with the originating device_id and discard it without crashing.
5. THE Aggregation_Service SHALL run as a Docker container on the Main_Device and restart automatically on failure.

---

### Requirement 5: Live Video Feed Streaming

**User Story:** As an operator, I want to view live video from each edge device in the control center, so that I can visually monitor the camera feeds alongside tracking data.

#### Acceptance Criteria

1. THE Edge_Device SHALL stream live video to the Main_Device using WebRTC.
2. WHEN an Operator requests a Live_Feed in the Control_Center, THE Control_Center SHALL display the WebRTC stream from the selected Edge_Device within 3 seconds.
3. THE Control_Center SHALL overlay real-time bounding boxes and track IDs from the Tracking_Payload onto the corresponding Live_Feed.
4. WHILE a Live_Feed is active, THE Control_Center SHALL update the tracking overlay at the same rate as incoming Tracking_Payloads.
5. IF a Live_Feed stream is interrupted, THEN THE Control_Center SHALL display a visual indicator to the Operator and attempt to reconnect automatically.

---

### Requirement 6: Control Center Web UI

**User Story:** As an operator, I want a local web interface to monitor all edge devices and their detections, so that I can manage the system from a single screen.

#### Acceptance Criteria

1. THE Control_Center SHALL be accessible via a web browser on the local network at a configurable URL (default: `http://<main_device_ip>:8080`).
2. THE Control_Center SHALL display a dashboard listing all registered Edge_Devices with their current online/offline status.
3. WHEN an Operator selects an Edge_Device from the dashboard, THE Control_Center SHALL display the Live_Feed and real-time tracking overlay for that device.
4. THE Control_Center SHALL support displaying up to 4 simultaneous Live_Feeds in a grid layout, and THE system SHALL support 5 or more simultaneously connected Edge_Devices.
5. THE Control_Center SHALL update the device status list within 2 seconds of an Edge_Device connecting or disconnecting.

---

### Requirement 7: Operator Control of Edge Device Streams

**User Story:** As an operator, I want to start and stop inference streams on individual edge devices from the control center, so that I can manage system resources and focus on areas of interest.

#### Acceptance Criteria

1. WHEN an Operator issues a start command for an Edge_Device, THE Control_Center SHALL publish a command to the MQTT topic `uav/command/{device_id}` with action `start_stream`.
2. WHEN an Operator issues a stop command for an Edge_Device, THE Control_Center SHALL publish a command to the MQTT topic `uav/command/{device_id}` with action `stop_stream`.
3. WHEN THE Edge_Device receives a `stop_stream` command, THE Edge_Device SHALL cease publishing Tracking_Payloads and suspend the Live_Feed stream within 2 seconds.
4. WHEN THE Edge_Device receives a `start_stream` command, THE Edge_Device SHALL resume publishing Tracking_Payloads and the Live_Feed stream within 3 seconds.
5. IF a command is published but no acknowledgement is received within 5 seconds, THEN THE Control_Center SHALL display a timeout warning to the Operator.

---

### Requirement 8: Docker Orchestration on Main Device

**User Story:** As a system administrator, I want all main device services to be orchestrated via Docker, so that deployment, scaling, and recovery are manageable.

#### Acceptance Criteria

1. THE Main_Device SHALL run the MQTT_Broker, Aggregation_Service, and Control_Center as separate Docker containers defined in a single Docker Compose file.
2. WHEN the Docker Compose stack is started, THE Main_Device SHALL bring up all services in dependency order (MQTT_Broker first, then Aggregation_Service and Control_Center).
3. IF any Docker container exits unexpectedly, THEN Docker SHALL automatically restart the container using the `unless-stopped` restart policy.
4. THE Docker Compose configuration SHALL expose only the necessary ports to the local network and bind all services to the host's local network interface.
5. THE Main_Device SHALL provide a single `docker compose up -d` command to start the entire system.

---

### Requirement 9: Tracking Payload Schema and Round-Trip Integrity

**User Story:** As a system integrator, I want a well-defined and validated tracking payload format, so that all components can reliably parse and process detection data.

#### Acceptance Criteria

1. THE Tracking_Payload SHALL conform to a published JSON schema containing: `device_id` (string), `timestamp` (ISO 8601 UTC string), `frame_id` (integer), `detections` (array of objects each with `track_id`, `bbox` [x, y, w, h], `confidence` (float 0.0–1.0), `label` (string)).
2. THE Aggregation_Service SHALL validate every received Tracking_Payload against the published JSON schema.
3. THE Edge_Device SHALL serialize Tracking_Payloads to JSON and THE Aggregation_Service SHALL deserialize them such that for all valid Tracking_Payloads, serialization then deserialization produces an equivalent object (round-trip property).
4. IF a `confidence` value outside the range [0.0, 1.0] is received, THEN THE Aggregation_Service SHALL reject the payload and log a validation error with the originating device_id.

---

### Requirement 10: Configuration Management

**User Story:** As a system administrator, I want all system parameters to be externally configurable, so that the system can be adapted to different deployments without code changes.

#### Acceptance Criteria

1. THE Edge_Device SHALL read all runtime parameters (MQTT broker host/port, camera source, model path, device ID, target frame rate) from a configuration file or environment variables at startup.
2. THE Main_Device services SHALL read all runtime parameters (broker port, TLS settings, aggregation service endpoints, control center port) from environment variables defined in a `.env` file co-located with the Docker Compose file.
3. IF a required configuration parameter is missing at startup, THEN THE affected service SHALL log the missing parameter name and exit with a non-zero status code.

---

### Requirement 11: Data Security in Transit

**User Story:** As a system administrator, I want all data transmitted between system components to be encrypted and authenticated, so that the system is protected against eavesdropping and unauthorized access.

#### Acceptance Criteria

1. THE system SHALL encrypt all MQTT traffic between Edge_Devices and the MQTT_Broker using TLS.
2. THE system SHALL encrypt all WebRTC video streams between Edge_Devices and the Control_Center using DTLS-SRTP as mandated by the WebRTC standard.
3. THE MQTT_Broker SHALL require each connecting client to authenticate using either a valid TLS client certificate or a username/password credential before accepting any messages.
4. THE Main_Device services SHALL store TLS certificates and credentials outside of version control in a configurable secrets path.
5. IF a client attempts to connect to the MQTT_Broker without valid authentication, THEN THE MQTT_Broker SHALL reject the connection and log the attempt with the client's IP address.

---

### Requirement 12: Map Layout with Device Locations and Detection Alerts

**User Story:** As an operator, I want an interactive map showing the geographic locations of all edge devices and their detection alerts, so that I can quickly identify which physical area a UAV detection is occurring in.

#### Acceptance Criteria

1. THE Control_Center SHALL display an interactive map rendered using an open-source tile-based library (e.g., Leaflet.js with OpenStreetMap tiles) showing a marker for each registered Edge_Device at its configured geographic coordinates.
2. THE Edge_Device location (latitude/longitude) SHALL be read from the device configuration file at deployment time and SHALL remain fixed during runtime.
3. WHEN a detection is confirmed by an Edge_Device, THE Control_Center SHALL update the corresponding device marker to display a visual alert (e.g., pulsing indicator, color change, or alert icon) within 2 seconds of the detection event.
4. THE visual alert marker SHALL display the device_id, UTC timestamp of the detection, and the number of detections in the current detection event.
5. WHEN an Operator dismisses an alert, THE Control_Center SHALL remove the visual alert state from the corresponding marker.
6. WHEN a detection event clears (no detections received for a configurable timeout period), THE Control_Center SHALL automatically remove the visual alert state from the corresponding marker.
7. THE Control_Center SHALL reflect each Edge_Device's online/offline status on the map using distinct marker colors (e.g., green for online, grey for offline).
8. THE Control_Center map SHALL function fully without an external tile server by using self-hosted or pre-cached map tiles, with no dependency on internet connectivity in production.
9. THE MQTT_Broker SHALL accept TLS-encrypted connections from Edge_Devices connecting over the internet (not limited to the local network), with the broker's public hostname or IP address configurable via the `.env` file.
10. THE Control_Center map SHALL display Edge_Devices connected over the internet using the same marker and alert mechanisms as locally connected devices, with no distinction in the UI based on network topology.

---

### Requirement 13: PTZ Camera Control (Pan, Tilt, Zoom)

**User Story:** As an operator, I want to control the pan, tilt, and zoom of edge device cameras from the control center, so that I can track a detected UAV and get a closer visual on it.

#### Acceptance Criteria

1. WHERE a device has PTZ capability enabled in its configuration, THE Control_Center SHALL display PTZ controls (joystick-style or directional button controls) in the Live_Feed view for that device.
2. WHEN an Operator issues a PTZ command, THE Control_Center SHALL publish the command to the MQTT topic `uav/ptz/{device_id}` as a JSON message containing the command type and any associated parameters.
3. THE PTZ command set SHALL include: `zoom_in`, `zoom_out`, `zoom_set` (with absolute zoom level parameter), `rotate_left`, `rotate_right`, `rotate_set` (with absolute pan angle parameter), `tilt_up`, `tilt_down`, `tilt_set` (with absolute tilt angle parameter), and `reset_home`.
4. THE Edge_Device SHALL support digital zoom (software-based processing applied to the video stream) for all devices and optical zoom (hardware commands) for devices with PTZ-capable cameras.
5. WHEN an Edge_Device with a hardware PTZ camera receives a PTZ command, THE Edge_Device SHALL translate the command into the appropriate hardware protocol (e.g., VISCA, ONVIF, or a configurable serial/IP protocol) as specified in the device configuration.
6. WHERE a device does not have PTZ capability enabled, THE Edge_Device SHALL silently ignore any PTZ commands received on `uav/ptz/{device_id}` without logging an error.
7. WHEN an Edge_Device executes a PTZ command, THE Edge_Device SHALL publish the resulting PTZ status (current zoom level, pan angle, tilt angle) to `uav/ptz/status/{device_id}`.
8. THE Edge_Device PTZ hardware protocol SHALL be configurable per device via the device configuration file, supporting at minimum VISCA over serial, VISCA over IP, and ONVIF.

---

### Requirement 14: Radar System Integration (Optional)

**User Story:** As an operator, I want the system to optionally ingest data from existing radar-based UAV detection systems, so that radar tracks can be correlated with camera detections for a more complete operational picture.

#### Acceptance Criteria

1. WHERE radar integration is enabled in configuration, THE Aggregation_Service SHALL accept radar track data via a configurable interface — either a dedicated MQTT topic `uav/radar/{radar_id}` or a REST endpoint.
2. WHEN radar track data is received, THE Aggregation_Service SHALL normalize it into the standard Tracking_Payload schema with `label` set to `"radar"` and a `source` field identifying the originating Radar_Source.
3. THE Control_Center map SHALL display radar tracks alongside camera-based detections using a distinct visual indicator that differentiates radar-sourced detections from camera-sourced detections.
4. THE radar integration SHALL be disabled by default and enabled via a configuration flag in the `.env` file.
5. IF radar integration is enabled but the Radar_Source is unreachable, THEN THE Aggregation_Service SHALL log a warning and continue operating using only camera-based detection data.

---

### Requirement 15: Remote Access to Control Center

**User Story:** As an operator, I want to access the control center from outside the local network, so that I can monitor and manage the system remotely.

#### Acceptance Criteria

1. THE Control_Center SHALL be accessible remotely via a WireGuard-based VPN tunnel (or equivalent) as the primary secure remote access method, allowing authorized remote Operators to access the Control_Center as if on the local network.
2. WHERE non-VPN remote access is enabled via configuration, THE Control_Center SHALL be exposed on a public-facing port with HTTPS (TLS) and token-based authentication.
3. WHEN operating in non-VPN remote access mode, THE Control_Center SHALL enforce HTTPS and require a valid API token or session token for all requests.
4. THE remote access mode (VPN / non-VPN / local-only) SHALL be configurable via environment variables in the Docker Compose `.env` file.
5. IF non-VPN remote access is enabled, THEN THE system SHALL log a warning at startup indicating that VPN-less remote access is active.

---

### Requirement 16: Arduino-Based Camera Controller (Optional)

**User Story:** As a system integrator, I want to optionally use Arduino-based motorized camera mounts as an alternative to full PTZ cameras, so that lower-cost hardware can be used for pan/tilt/zoom control.

#### Acceptance Criteria

1. WHERE Arduino-based camera control is enabled in the device configuration, THE Edge_Device SHALL receive PTZ commands from the Control_Center via the existing `uav/ptz/{device_id}` MQTT topic and forward them to the Arduino controller over a configurable serial (USB) connection.
2. THE Arduino firmware interface SHALL accept simple serial commands specifying pan angle, tilt angle, and zoom level (where supported by the hardware).
3. THE Arduino device type SHALL be configurable per edge device in the device configuration file as a distinct hardware type, separate from VISCA and ONVIF hardware types.
4. THE camera mounted on an Arduino rig SHALL be treated as a standard camera source by the Inference_Engine, supporting USB camera and IP camera input modes.
5. THE Arduino-based camera controller capability SHALL be disabled by default and enabled via the device configuration file.

---

### Requirement 17: UAV Distance and Trajectory Estimation (Optional)

**User Story:** As an operator, I want the system to optionally estimate the distance and trajectory of a detected UAV, so that I can assess the threat level and predict its flight path.

#### Acceptance Criteria

1. WHERE distance estimation is enabled in device configuration, THE Inference_Engine SHALL estimate the approximate distance to a detected UAV using the apparent bounding box size relative to the frame dimensions and a configurable known UAV reference size (wingspan or body length in meters) as a required parameter.
2. WHERE trajectory estimation is enabled in device configuration, THE Inference_Engine SHALL compute a velocity vector (direction and speed in pixels/frame) from the sequence of bounding box positions across frames, convertible to approximate real-world units when distance is known.
3. WHERE a camera device provides compass and pitch sensor data (e.g., a smartphone used as an IP camera source), THE Edge_Device SHALL include the compass bearing and pitch in the Tracking_Payload as an optional `sensor_data` field with the structure `{ "compass_bearing_deg": float, "pitch_deg": float }`.
4. THE system SHALL support smartphones as IP camera sources via a configurable stream URL (e.g., from an IP Webcam application), with sensor data published separately to the MQTT topic `uav/sensor/{device_id}` as a JSON Sensor_Payload.
5. WHEN distance and trajectory estimation are enabled, THE Edge_Device SHALL include the estimated distance and trajectory in the Tracking_Payload as optional fields `estimated_distance_m` and `trajectory_vector`.
6. WHEN `estimated_distance_m` and `trajectory_vector` are present in a Tracking_Payload, THE Control_Center SHALL display them in the Live_Feed overlay and on the map view.
7. THE distance and trajectory estimation capability SHALL be disabled by default and enabled via device configuration, with the reference UAV size as a required parameter when enabled.

---

### Requirement 18: Dynamic Model Switching

**User Story:** As an operator, I want to switch the active YOLO model on an edge device at runtime from the control center, so that I can use the most appropriate detection model for current lighting and camera conditions without restarting the device.

#### Acceptance Criteria

1. THE Inference_Engine SHALL support a configurable library of named model profiles, each specifying a `name` (string), `file_path` (path to a `.pt` weights file), and `camera_mode` (string: `"daylight"`, `"night"`, or `"thermal"`).
2. Model profiles SHALL be configurable per device in the device configuration file, allowing different Edge_Devices to have different sets of available model profiles.
3. WHEN an Operator issues a model switch command for an Edge_Device, THE Control_Center SHALL publish a command to the MQTT topic `uav/command/{device_id}` as a JSON message with `action` set to `"switch_model"` and a `model_name` parameter identifying the target profile.
4. WHEN THE Edge_Device receives a `switch_model` command, THE Edge_Device SHALL hot-swap the active model within a configurable timeout (default 5 seconds) without dropping the camera feed or MQTT connection.
5. WHILE a model switch is in progress, THE Edge_Device SHALL pause publishing Tracking_Payloads and SHALL resume publishing immediately after the new model is loaded.
6. IF a requested model profile's `file_path` does not resolve to an existing file, THEN THE Edge_Device SHALL log an error, retain the currently active model without interruption, and publish an error status to `uav/status/{device_id}`.
7. THE Edge_Device SHALL include the currently active model profile name in its retained `uav/status/{device_id}` status message.
8. THE Control_Center SHALL display the currently active model profile name for each Edge_Device in the device dashboard.
9. THE Control_Center SHALL provide a model selector UI per device that lists all model profiles configured for that device, allowing the Operator to issue a model switch command from the dashboard.
10. WHERE a model profile has `camera_mode` set to `"thermal"`, THE Inference_Engine SHALL apply thermal-specific preprocessing (e.g., colormap normalization) to each camera frame before passing it to the model for inference.
