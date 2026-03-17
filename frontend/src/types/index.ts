// Shared TypeScript interfaces for the UAV Control Center frontend

export interface TrajectoryVector {
  dx: number;
  dy: number;
}

export interface Detection {
  track_id: number;
  bbox: [number, number, number, number]; // [x, y, w, h]
  confidence: number;
  label: string;
  estimated_distance_m?: number;
  trajectory_vector?: TrajectoryVector;
}

export interface SensorData {
  compass_bearing_deg: number;
  pitch_deg: number;
}

export interface TrackingPayload {
  device_id: string;
  timestamp: string;
  frame_id: number;
  active_model?: string;
  source?: "camera" | "radar";
  detections: Detection[];
  sensor_data?: SensorData;
}

export interface PtzStatus {
  device_id: string;
  last_command: string;
  success: boolean;
  timestamp: string;
  zoom_level?: number;
  pan_offset?: number;
  tilt_offset?: number;
}

export interface DeviceState {
  device_id: string;
  status: "online" | "offline" | "unknown";
  active_model: string | null;
  lat: number | null;
  lon: number | null;
  last_status_ts: string | null;
  detection_count: number;
  last_tracking: TrackingPayload | null;
  last_ptz_status: PtzStatus | null;
  last_sensor: SensorData | null;
}

export interface PtzCommand {
  command:
    | "pan_left"
    | "pan_right"
    | "tilt_up"
    | "tilt_down"
    | "zoom_in"
    | "zoom_out"
    | "pan_tilt_absolute"
    | "zoom_absolute"
    | "stop"
    | "home";
  params?: Record<string, number>;
}

export interface CommandPayload {
  action: "start_stream" | "stop_stream" | "switch_model";
  model_name?: string;
}

export interface ModelProfile {
  name: string;
  file_path: string;
  camera_mode: "daylight" | "night" | "thermal";
  description?: string;
}

export interface WebSocketMessage {
  type?: "snapshot";
  device_id?: string;
  state?: DeviceState;
  devices?: DeviceState[];
}
