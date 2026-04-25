/**
 * Logs page — filterable log table from all edge devices.
 * Color-coded by level, auto-scrolls to latest, pauses on hover.
 * Export to CSV button.
 *
 * Requirements: v2-7.6, v2-7.7, v2-7.8, v2-7.9
 */

import React, { useEffect, useRef, useState, useCallback } from "react";
import { useDevices } from "../api/websocket";
import { authFetch } from "../utils/auth";

interface LogEntry {
  timestamp: string;
  level: "WARNING" | "ERROR" | "CRITICAL";
  logger: string;
  message: string;
  device_id: string;
}

const LEVEL_COLORS: Record<string, string> = {
  WARNING: "var(--uav-color-warning)",
  ERROR: "var(--ha-color-orange-60)",
  CRITICAL: "var(--uav-color-alert)",
};

const LEVEL_BG: Record<string, string> = {
  WARNING: "color-mix(in srgb, var(--uav-color-warning) 8%, transparent)",
  ERROR: "color-mix(in srgb, var(--ha-color-orange-60) 8%, transparent)",
  CRITICAL: "color-mix(in srgb, var(--uav-color-alert) 8%, transparent)",
};

export function LogsPage() {
  const devices = useDevices();
  const deviceIds = ["all", ...Object.keys(devices)];

  const [selectedDevice, setSelectedDevice] = useState("all");
  const [selectedLevel, setSelectedLevel] = useState("all");
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [paused, setPaused] = useState(false);
  const tableRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Export detections modal state
  const [showExport, setShowExport] = useState(false);
  const [exportDevice, setExportDevice] = useState("");
  const [exportFrom, setExportFrom] = useState("");
  const [exportTo, setExportTo] = useState("");

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const deviceList = selectedDevice === "all" ? Object.keys(devices) : [selectedDevice];
      const allEntries: LogEntry[] = [];
      for (const did of deviceList) {
        const params = new URLSearchParams({ limit: "200" });
        if (selectedLevel !== "all") params.set("level", selectedLevel);
        const resp = await authFetch(`/api/logs/${did}?${params}`);
        if (resp.ok) {
          const data = await resp.json();
          allEntries.push(...data);
        }
      }
      // Sort by timestamp descending
      allEntries.sort((a, b) => b.timestamp.localeCompare(a.timestamp));
      setEntries(allEntries.slice(0, 500));
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [selectedDevice, selectedLevel, devices]);

  useEffect(() => {
    fetchLogs();
    const interval = setInterval(fetchLogs, 5000);
    return () => clearInterval(interval);
  }, [fetchLogs]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (!paused && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [entries, paused]);

  const exportCsv = () => {
    const header = "timestamp,level,device_id,logger,message\n";
    const rows = entries.map((e) =>
      [e.timestamp, e.level, e.device_id, e.logger, `"${e.message.replace(/"/g, '""')}"`].join(",")
    );
    const blob = new Blob([header + rows.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `uav-logs-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleExportDetections = () => {
    if (!exportDevice) return;
    const params = new URLSearchParams({ format: "csv" });
    if (exportFrom) params.set("from", exportFrom);
    if (exportTo) params.set("to", exportTo);
    window.location.href = `/api/devices/${exportDevice}/detections/export?${params}`;
    setShowExport(false);
  };

  return (
    <div style={{ padding: "var(--ha-space-6)", display: "flex", flexDirection: "column", gap: "var(--ha-space-4)", height: "100%" }}>
      {/* Filter bar */}
      <div style={{ display: "flex", gap: "var(--ha-space-3)", alignItems: "center", flexWrap: "wrap" }}>
        <label style={labelStyle}>Device:</label>
        <select value={selectedDevice} onChange={(e) => setSelectedDevice(e.target.value)} style={selectStyle}>
          {deviceIds.map((id) => <option key={id} value={id}>{id === "all" ? "All Devices" : id}</option>)}
        </select>

        <label style={labelStyle}>Level:</label>
        <select value={selectedLevel} onChange={(e) => setSelectedLevel(e.target.value)} style={selectStyle}>
          <option value="all">All Levels</option>
          <option value="WARNING">WARNING</option>
          <option value="ERROR">ERROR</option>
          <option value="CRITICAL">CRITICAL</option>
        </select>

        <button onClick={fetchLogs} style={btnStyle} disabled={loading}>
          {loading ? "Loading…" : "Refresh"}
        </button>
        <button onClick={exportCsv} style={btnStyle} disabled={entries.length === 0}>
          Export CSV
        </button>
        <button onClick={() => setShowExport(true)} style={btnStyle}>
          Export Detections
        </button>
        <span style={{ fontSize: "var(--ha-font-size-xs)", color: "var(--secondary-text-color)", marginLeft: "auto" }}>
          {entries.length} entries
        </span>
      </div>

      {/* Export Detections modal */}
      {showExport && (
        <div style={{
          position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)",
          display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
        }} onClick={() => setShowExport(false)}>
          <div style={{
            background: "var(--card-background-color)", borderRadius: "var(--ha-border-radius-lg)",
            padding: "var(--ha-space-5)", minWidth: 320, display: "flex", flexDirection: "column", gap: "var(--ha-space-3)",
          }} onClick={(e) => e.stopPropagation()}>
            <div style={{ fontSize: "var(--ha-font-size-m)", fontWeight: "bold" }}>Export Detections</div>
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--ha-space-2)" }}>
              <label style={labelStyle}>Device:</label>
              <select value={exportDevice} onChange={(e) => setExportDevice(e.target.value)} style={selectStyle}>
                <option value="">Select device…</option>
                {Object.keys(devices).map((id) => <option key={id} value={id}>{id}</option>)}
              </select>
              <label style={labelStyle}>From:</label>
              <input type="datetime-local" value={exportFrom} onChange={(e) => setExportFrom(e.target.value)} style={selectStyle} />
              <label style={labelStyle}>To:</label>
              <input type="datetime-local" value={exportTo} onChange={(e) => setExportTo(e.target.value)} style={selectStyle} />
            </div>
            <div style={{ display: "flex", gap: "var(--ha-space-2)" }}>
              <button onClick={handleExportDetections} style={btnStyle} disabled={!exportDevice}>Download CSV</button>
              <button onClick={() => setShowExport(false)} style={btnStyle}>Cancel</button>
            </div>
          </div>
        </div>
      )}

      {/* Log table */}
      <div
        ref={tableRef}
        onMouseEnter={() => setPaused(true)}
        onMouseLeave={() => setPaused(false)}
        style={{
          flex: 1,
          overflowY: "auto",
          background: "var(--card-background-color)",
          border: "1px solid var(--divider-color)",
          borderRadius: "var(--ha-border-radius-lg)",
          fontFamily: "var(--ha-font-family-code)",
          fontSize: "var(--ha-font-size-xs)",
        }}
      >
        {entries.length === 0 ? (
          <div style={{ padding: "var(--ha-space-6)", color: "var(--secondary-text-color)", textAlign: "center" }}>
            No log entries.
          </div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead style={{ position: "sticky", top: 0, background: "var(--card-background-color)", zIndex: 1 }}>
              <tr style={{ borderBottom: "1px solid var(--divider-color)" }}>
                <th style={thStyle}>Time</th>
                <th style={thStyle}>Level</th>
                <th style={thStyle}>Device</th>
                <th style={thStyle}>Logger</th>
                <th style={{ ...thStyle, width: "50%" }}>Message</th>
              </tr>
            </thead>
            <tbody>
              {[...entries].reverse().map((entry, i) => (
                <tr
                  key={i}
                  style={{
                    borderBottom: "1px solid var(--divider-color)",
                    background: LEVEL_BG[entry.level] ?? "transparent",
                  }}
                >
                  <td style={tdStyle}>{new Date(entry.timestamp).toLocaleTimeString()}</td>
                  <td style={{ ...tdStyle, color: LEVEL_COLORS[entry.level], fontWeight: "bold" }}>
                    {entry.level}
                  </td>
                  <td style={tdStyle}>{entry.device_id}</td>
                  <td style={{ ...tdStyle, color: "var(--secondary-text-color)" }}>{entry.logger}</td>
                  <td style={tdStyle}>{entry.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

const labelStyle: React.CSSProperties = {
  fontSize: "var(--ha-font-size-s)",
  color: "var(--secondary-text-color)",
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

const thStyle: React.CSSProperties = {
  padding: "var(--ha-space-2) var(--ha-space-3)",
  textAlign: "left",
  color: "var(--secondary-text-color)",
  fontWeight: "normal",
  fontSize: "var(--ha-font-size-xs)",
};

const tdStyle: React.CSSProperties = {
  padding: "var(--ha-space-1) var(--ha-space-3)",
  verticalAlign: "top",
};
