/**
 * Device Detail page — full-page view for a single edge device.
 * Shows health, cert info, connection timeline, model info, detection history,
 * edit config panel, IP webcam controls, and sensor data.
 *
 * Requirements: v2-4.1 through v2-4.7, 23.1–23.5
 */

import React, { useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useDevice } from "../api/websocket";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { StatChip } from "../components/ui/StatChip";
import { HealthGauges } from "../components/HealthGauges";
import { formatUptime } from "../utils/formatUptime";
import { getClassColor } from "../utils/classColors";
import { authFetch } from "../utils/auth";

export function DeviceDetailPage() {
  const { device_id } = useParams<{ device_id: string }>();
  const navigate = useNavigate();
  const device = useDevice(device_id ?? "");

  if (!device) {
    return (
      <div style={{ padding: "var(--ha-space-6)", color: "var(--secondary-text-color)" }}>
        Device <code>{device_id}</code> not found.{" "}
        <button onClick={() => navigate("/")} style={linkBtnStyle}>← Back</button>
      </div>
    );
  }

  const health = device.health;
  const cert = device.cert_info;
  const certExpiringSoon = cert ? isExpiringSoon(cert.expires_at) : false;
  const statusVariant = device.status === "online" ? "online"
    : device.status === "offline" ? "offline"
    : device.status === "health_timeout" ? "warning"
    : "unknown";

  return (
    <div style={{ padding: "var(--ha-space-6)", display: "flex", flexDirection: "column", gap: "var(--ha-space-4)" }}>
      <button onClick={() => navigate(-1)} style={linkBtnStyle}>← Back</button>

      {/* Header */}
      <Card>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--ha-space-3)" }}>
          <Badge variant={statusVariant} />
          <h1 style={{ margin: 0, fontFamily: "var(--ha-font-family-code)", fontSize: "var(--ha-font-size-2xl)", fontWeight: "var(--ha-font-weight-bold)" as any }}>
            {device.device_id}
          </h1>
          {health && (
            <span style={{ fontSize: "var(--ha-font-size-s)", color: "var(--secondary-text-color)" }}>
              Uptime: {formatUptime(health.uptime_s)}
            </span>
          )}
        </div>
      </Card>

      {/* Health metrics */}
      {health && (
        <Card>
          <SectionTitle>Health Metrics</SectionTitle>
          <HealthGauges health={health} />
          {device.ipwebcam_sensors && <IpWebcamSensors sensors={device.ipwebcam_sensors} />}
        </Card>
      )}

      {/* Authorization / cert info */}
      <Card>
        <SectionTitle>
          Authorization
          {certExpiringSoon && (
            <StatChip label="Expiring soon" color="var(--uav-color-warning)" style={{ marginLeft: "var(--ha-space-2)" }} />
          )}
        </SectionTitle>
        {cert ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--ha-space-2)" }}>
            <Row label="CN" value={cert.cn} />
            <Row label="Issuer" value={cert.issuer} />
            <Row label="Expires" value={new Date(cert.expires_at).toLocaleDateString()} />
          </div>
        ) : (
          <span style={{ color: "var(--secondary-text-color)", fontSize: "var(--ha-font-size-s)" }}>
            No certificate info available.
          </span>
        )}
        {device.last_status_ts && (
          <Row label="Last Auth" value={new Date(device.last_status_ts).toLocaleString()} />
        )}
      </Card>

      {/* Model info */}
      <Card>
        <SectionTitle>Model</SectionTitle>
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--ha-space-2)" }}>
          <Row label="Active Model" value={device.active_model ?? "—"} />
          {device.last_tracking?.active_model && device.last_tracking.active_model !== device.active_model && (
            <Row label="Last Seen Model" value={device.last_tracking.active_model} />
          )}
        </div>
      </Card>

      {/* Edit Config */}
      <EditConfigPanel device_id={device.device_id} currentModel={device.active_model} />

      {/* IP Webcam Controls */}
      {device.ipwebcam_capabilities && (
        <IpWebcamPanel device_id={device.device_id} capabilities={device.ipwebcam_capabilities} />
      )}

      {/* Detection history */}
      <Card>
        <SectionTitle>Recent Detections</SectionTitle>
        {device.last_tracking?.detections && device.last_tracking.detections.length > 0 ? (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "var(--ha-font-size-s)" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--divider-color)", textAlign: "left" }}>
                <th style={thStyle}>Time</th>
                <th style={thStyle}>Label</th>
                <th style={thStyle}>Confidence</th>
                <th style={thStyle}>Track ID</th>
              </tr>
            </thead>
            <tbody>
              {device.last_tracking.detections.slice(0, 50).map((det, i) => (
                <tr key={i} style={{ borderBottom: "1px solid var(--divider-color)" }}>
                  <td style={tdStyle}>{new Date(device.last_tracking!.timestamp).toLocaleTimeString()}</td>
                  <td style={tdStyle}>
                    <StatChip label={det.label} color={getClassColor(det.label, det.confidence)} />
                  </td>
                  <td style={tdStyle}>{(det.confidence * 100).toFixed(0)}%</td>
                  <td style={tdStyle}>#{det.track_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <span style={{ color: "var(--secondary-text-color)", fontSize: "var(--ha-font-size-s)" }}>No recent detections.</span>
        )}
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Edit Config Panel (23.1)
// ---------------------------------------------------------------------------

function EditConfigPanel({ device_id, currentModel }: { device_id: string; currentModel: string | null }) {
  const [cameraSource, setCameraSource] = useState("");
  const [fps, setFps] = useState("");
  const [activeModel, setActiveModel] = useState(currentModel ?? "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload: Record<string, any> = { action: "update_config" };
    if (cameraSource) payload.camera_source = cameraSource;
    if (fps) payload.fps = Number(fps);
    if (activeModel && activeModel !== currentModel) payload.active_model = activeModel;
    if (Object.keys(payload).length === 1) return; // only action key, nothing changed
    setSaving(true);
    try {
      await authFetch(`/api/command/${device_id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <SectionTitle>Edit Config</SectionTitle>
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "var(--ha-space-3)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--ha-space-3)" }}>
          <label style={labelStyle}>Camera Source:</label>
          <input
            value={cameraSource}
            onChange={(e) => setCameraSource(e.target.value)}
            placeholder="e.g. /dev/video0 or rtsp://..."
            style={{ ...inputStyle, flex: 1 }}
          />
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--ha-space-3)" }}>
          <label style={labelStyle}>FPS:</label>
          <input
            type="number" min={1} max={120}
            value={fps}
            onChange={(e) => setFps(e.target.value)}
            placeholder="e.g. 30"
            style={{ ...inputStyle, width: 100 }}
          />
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--ha-space-3)" }}>
          <label style={labelStyle}>Active Model:</label>
          <input
            value={activeModel}
            onChange={(e) => setActiveModel(e.target.value)}
            placeholder="model name"
            style={{ ...inputStyle, flex: 1 }}
          />
        </div>
        <div>
          <button type="submit" style={btnStyle} disabled={saving}>
            {saved ? "Saved!" : saving ? "Saving…" : "Apply"}
          </button>
        </div>
      </form>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// IP Webcam Controls Panel (23.2 + 23.3 + 23.4)
// ---------------------------------------------------------------------------

function IpWebcamPanel({ device_id, capabilities }: { device_id: string; capabilities: Record<string, any> }) {
  const [zoom, setZoom] = useState(0);
  const [videoSize, setVideoSize] = useState<string>("");
  const [quality, setQuality] = useState(50);
  const [torch, setTorch] = useState(false);
  const [ffc, setFfc] = useState(false);
  const [nightVision, setNightVision] = useState(false);
  const [overlay, setOverlay] = useState(false);
  const [focusMode, setFocusMode] = useState<string>("");
  const [manualSensor, setManualSensor] = useState(false);
  const [iso, setIso] = useState(100);
  const [exposureTime, setExposureTime] = useState("");
  const [frameDuration, setFrameDuration] = useState("");
  const [aperture, setAperture] = useState("");
  const [exposureLock, setExposureLock] = useState(false);
  const [wbLock, setWbLock] = useState(false);
  const [videoRecording, setVideoRecording] = useState(false);
  const [snapshotModal, setSnapshotModal] = useState<string | null>(null);

  const videoSizes: string[] = capabilities.video_sizes ?? [];
  const focusModes: string[] = capabilities.focus_modes ?? [];
  const isoRange: [number, number] = capabilities.iso_range ?? [50, 3200];

  const sendControl = async (setting: string, value: any) => {
    await authFetch(`/api/command/${device_id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "ipwebcam_control", setting, value }),
    }).catch(() => {});
  };

  const handleSnapshot = async () => {
    await sendControl("snapshot", true);
    // snapshot image will arrive via WebSocket
  };

  // Listen for snapshot WebSocket messages
  useEffect(() => {
    // We listen on the global device store's WS — simplest approach is to
    // subscribe to window-level custom events dispatched by the WS handler.
    // Since we can't easily hook into the store here, we poll via a custom event.
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail?.device_id === device_id && detail?.snapshot) {
        setSnapshotModal(detail.snapshot);
      }
    };
    window.addEventListener("uav_ws_message", handler);
    return () => window.removeEventListener("uav_ws_message", handler);
  }, [device_id]);

  const downloadSnapshot = () => {
    if (!snapshotModal) return;
    const a = document.createElement("a");
    a.href = `data:image/jpeg;base64,${snapshotModal}`;
    a.download = `snapshot-${device_id}-${Date.now()}.jpg`;
    a.click();
  };

  return (
    <Card>
      <SectionTitle>IP Webcam Controls</SectionTitle>

      {/* Stream */}
      <SubSection title="Stream">
        <ControlRow label="Zoom">
          <input type="range" min={0} max={100} value={zoom}
            onChange={(e) => { setZoom(Number(e.target.value)); sendControl("zoom", Number(e.target.value)); }}
            style={{ flex: 1 }} />
          <span style={valueStyle}>{zoom}</span>
        </ControlRow>
        {videoSizes.length > 0 && (
          <ControlRow label="Video Size">
            <select value={videoSize} onChange={(e) => { setVideoSize(e.target.value); sendControl("video_size", e.target.value); }} style={selectStyle}>
              {videoSizes.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </ControlRow>
        )}
        <ControlRow label="Quality">
          <input type="range" min={0} max={100} value={quality}
            onChange={(e) => { setQuality(Number(e.target.value)); sendControl("quality", Number(e.target.value)); }}
            style={{ flex: 1 }} />
          <span style={valueStyle}>{quality}</span>
        </ControlRow>
      </SubSection>

      {/* Camera */}
      <SubSection title="Camera">
        <ControlRow label="Torch">
          <Toggle value={torch} onChange={(v) => { setTorch(v); sendControl("torch", v); }} />
        </ControlRow>
        <ControlRow label="Front Camera">
          <Toggle value={ffc} onChange={(v) => { setFfc(v); sendControl("ffc", v); }} />
        </ControlRow>
        <ControlRow label="Night Vision">
          <Toggle value={nightVision} onChange={(v) => { setNightVision(v); sendControl("night_vision", v); }} />
        </ControlRow>
        <ControlRow label="Overlay">
          <Toggle value={overlay} onChange={(v) => { setOverlay(v); sendControl("overlay", v); }} />
        </ControlRow>
      </SubSection>

      {/* Focus */}
      <SubSection title="Focus">
        {focusModes.length > 0 && (
          <ControlRow label="Focus Mode">
            <select value={focusMode} onChange={(e) => { setFocusMode(e.target.value); sendControl("focus_mode", e.target.value); }} style={selectStyle}>
              {focusModes.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </ControlRow>
        )}
        <ControlRow label="">
          <button style={btnStyle} onClick={() => sendControl("focus", true)}>Focus</button>
        </ControlRow>
      </SubSection>

      {/* Exposure */}
      <SubSection title="Exposure">
        <ControlRow label="Manual Sensor">
          <Toggle value={manualSensor} onChange={(v) => { setManualSensor(v); sendControl("manual_sensor", v); }} />
        </ControlRow>
        <ControlRow label={`ISO (${isoRange[0]}–${isoRange[1]})`}>
          <input type="range" min={isoRange[0]} max={isoRange[1]} value={iso} disabled={!manualSensor}
            onChange={(e) => { setIso(Number(e.target.value)); sendControl("iso", Number(e.target.value)); }}
            style={{ flex: 1 }} />
          <span style={valueStyle}>{iso}</span>
        </ControlRow>
        <ControlRow label="Exposure Time (ms)">
          <input type="number" value={exposureTime} disabled={!manualSensor}
            onChange={(e) => setExposureTime(e.target.value)}
            onBlur={() => { if (exposureTime) sendControl("exposure_time", Number(exposureTime) * 1_000_000); }}
            style={{ ...inputStyle, width: 100 }} placeholder="ms" />
        </ControlRow>
        <ControlRow label="Frame Duration (ms)">
          <input type="number" value={frameDuration} disabled={!manualSensor}
            onChange={(e) => setFrameDuration(e.target.value)}
            onBlur={() => { if (frameDuration) sendControl("frame_duration", Number(frameDuration) * 1_000_000); }}
            style={{ ...inputStyle, width: 100 }} placeholder="ms" />
        </ControlRow>
        <ControlRow label="Aperture">
          <input type="number" value={aperture} disabled={!manualSensor}
            onChange={(e) => setAperture(e.target.value)}
            onBlur={() => { if (aperture) sendControl("aperture", Number(aperture)); }}
            style={{ ...inputStyle, width: 100 }} />
        </ControlRow>
        <ControlRow label="Exposure Lock">
          <Toggle value={exposureLock} onChange={(v) => { setExposureLock(v); sendControl("exposure_lock", v); }} />
        </ControlRow>
        <ControlRow label="White Balance Lock">
          <Toggle value={wbLock} onChange={(v) => { setWbLock(v); sendControl("whitebalance_lock", v); }} />
        </ControlRow>
      </SubSection>

      {/* Recording */}
      <SubSection title="Recording">
        <ControlRow label="Video Recording">
          <Toggle value={videoRecording} onChange={(v) => { setVideoRecording(v); sendControl("video_recording", v); }} />
        </ControlRow>
        <ControlRow label="">
          <button style={btnStyle} onClick={handleSnapshot}>Snapshot</button>
        </ControlRow>
      </SubSection>

      {/* Snapshot modal */}
      {snapshotModal && (
        <div style={{
          position: "fixed", inset: 0, background: "rgba(0,0,0,0.8)",
          display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
        }} onClick={() => setSnapshotModal(null)}>
          <div style={{ background: "var(--card-background-color)", borderRadius: "var(--ha-border-radius-lg)", padding: "var(--ha-space-4)", maxWidth: "90vw" }}
            onClick={(e) => e.stopPropagation()}>
            <img src={`data:image/jpeg;base64,${snapshotModal}`} alt="Snapshot" style={{ maxWidth: "80vw", maxHeight: "70vh", display: "block" }} />
            <div style={{ display: "flex", gap: "var(--ha-space-2)", marginTop: "var(--ha-space-3)" }}>
              <button style={btnStyle} onClick={downloadSnapshot}>Download</button>
              <button style={btnStyle} onClick={() => setSnapshotModal(null)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// IP Webcam Sensors (23.5)
// ---------------------------------------------------------------------------

function IpWebcamSensors({ sensors }: { sensors: Record<string, any> }) {
  const fields = ["battery_level", "battery_temp", "light", "motion", "pressure", "audio_connections"];
  const present = fields.filter((f) => sensors[f] !== undefined);
  if (present.length === 0) return null;
  return (
    <div style={{ marginTop: "var(--ha-space-3)", display: "flex", flexWrap: "wrap", gap: "var(--ha-space-2)" }}>
      {present.map((f) => (
        <StatChip key={f} label={f.replace(/_/g, " ")} count={sensors[f]} color="var(--secondary-text-color)" />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function SubSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: "var(--ha-space-3)" }}>
      <div style={{ fontSize: "var(--ha-font-size-xs)", color: "var(--secondary-text-color)", marginBottom: "var(--ha-space-1)", textTransform: "uppercase", letterSpacing: "0.04em" }}>{title}</div>
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--ha-space-2)" }}>{children}</div>
    </div>
  );
}

function ControlRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--ha-space-3)" }}>
      <span style={{ ...labelStyle, minWidth: 160 }}>{label}</span>
      <div style={{ display: "flex", alignItems: "center", gap: "var(--ha-space-2)", flex: 1 }}>{children}</div>
    </div>
  );
}

function Toggle({ value, onChange }: { value: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      onClick={() => onChange(!value)}
      style={{
        ...btnStyle,
        color: value ? "var(--uav-color-online)" : "var(--secondary-text-color)",
        borderColor: value ? "var(--uav-color-online)" : "var(--divider-color)",
      }}
    >
      {value ? "On" : "Off"}
    </button>
  );
}

function isExpiringSoon(expiresAt: string): boolean {
  try {
    const exp = new Date(expiresAt).getTime();
    const thirtyDays = 30 * 24 * 60 * 60 * 1000;
    return exp - Date.now() < thirtyDays;
  } catch {
    return false;
  }
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontSize: "var(--ha-font-size-s)", fontWeight: "var(--ha-font-weight-medium)" as any, color: "var(--secondary-text-color)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "var(--ha-space-3)" }}>
      {children}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", gap: "var(--ha-space-3)", alignItems: "baseline" }}>
      <span style={{ fontSize: "var(--ha-font-size-xs)", color: "var(--secondary-text-color)", minWidth: 120 }}>{label}</span>
      <span style={{ fontSize: "var(--ha-font-size-m)", fontFamily: "var(--ha-font-family-code)" }}>{value}</span>
    </div>
  );
}

const linkBtnStyle: React.CSSProperties = {
  background: "transparent",
  border: "none",
  color: "var(--primary-color)",
  cursor: "pointer",
  fontSize: "var(--ha-font-size-s)",
  padding: 0,
  fontFamily: "var(--ha-font-family-body)",
};

const btnStyle: React.CSSProperties = {
  background: "var(--secondary-background-color)",
  border: "1px solid var(--divider-color)",
  borderRadius: "var(--ha-border-radius-md)",
  color: "var(--secondary-text-color)",
  cursor: "pointer",
  fontSize: "var(--ha-font-size-s)",
  padding: "var(--ha-space-1) var(--ha-space-3)",
  fontFamily: "var(--ha-font-family-body)",
};

const selectStyle: React.CSSProperties = {
  background: "var(--secondary-background-color)",
  border: "1px solid var(--divider-color)",
  borderRadius: "var(--ha-border-radius-md)",
  color: "var(--primary-text-color)",
  fontSize: "var(--ha-font-size-s)",
  padding: "var(--ha-space-1) var(--ha-space-2)",
  fontFamily: "var(--ha-font-family-body)",
};

const inputStyle: React.CSSProperties = {
  background: "var(--secondary-background-color)",
  border: "1px solid var(--divider-color)",
  borderRadius: "var(--ha-border-radius-md)",
  color: "var(--primary-text-color)",
  fontSize: "var(--ha-font-size-s)",
  padding: "var(--ha-space-1) var(--ha-space-2)",
  fontFamily: "var(--ha-font-family-body)",
  outline: "none",
};

const labelStyle: React.CSSProperties = {
  fontSize: "var(--ha-font-size-s)",
  color: "var(--secondary-text-color)",
};

const valueStyle: React.CSSProperties = {
  fontSize: "var(--ha-font-size-s)",
  minWidth: 36,
  textAlign: "right" as const,
};

const thStyle: React.CSSProperties = { padding: "var(--ha-space-2) var(--ha-space-3)", color: "var(--secondary-text-color)" };
const tdStyle: React.CSSProperties = { padding: "var(--ha-space-2) var(--ha-space-3)" };
