/**
 * Collapsible left navigation sidebar.
 * Persists collapsed state in localStorage.
 */

import React, { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";

const STORAGE_KEY = "uav_sidebar_collapsed";

interface NavItem {
  id: string;
  label: string;
  path: string;
  icon: React.ReactNode;
}

const NAV_ITEMS: NavItem[] = [
  { id: "overview", label: "Overview", path: "/", icon: <GridIcon /> },
  { id: "map", label: "Map", path: "/map", icon: <MapIcon /> },
  { id: "feeds", label: "Live Feeds", path: "/feeds", icon: <VideoIcon /> },
  { id: "devices", label: "Devices", path: "/devices", icon: <DeviceIcon /> },
  { id: "ptz", label: "PTZ", path: "/ptz", icon: <PtzIcon /> },
  { id: "logs", label: "Logs", path: "/logs", icon: <LogIcon /> },
  { id: "settings", label: "Settings", path: "/settings", icon: <SettingsIcon /> },
];

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(() => {
    return localStorage.getItem(STORAGE_KEY) === "true";
  });
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, String(collapsed));
  }, [collapsed]);

  const width = collapsed ? "var(--sidebar-width-collapsed)" : "var(--sidebar-width-expanded)";

  return (
    <aside
      style={{
        width,
        minWidth: width,
        height: "100vh",
        background: "var(--card-background-color)",
        borderRight: "1px solid var(--divider-color)",
        display: "flex",
        flexDirection: "column",
        transition: "width 0.2s ease, min-width 0.2s ease",
        overflow: "hidden",
        position: "sticky",
        top: 0,
        zIndex: 100,
      }}
    >
      {/* Logo area */}
      <div style={{
        height: "var(--topbar-height)",
        display: "flex",
        alignItems: "center",
        padding: "0 var(--ha-space-4)",
        borderBottom: "1px solid var(--divider-color)",
        gap: "var(--ha-space-3)",
        flexShrink: 0,
      }}>
        <RadarIcon />
        {!collapsed && (
          <span style={{
            fontSize: "var(--ha-font-size-s)",
            fontWeight: "var(--ha-font-weight-bold)" as any,
            color: "var(--primary-text-color)",
            whiteSpace: "nowrap",
            overflow: "hidden",
          }}>
            Anti-UAV
          </span>
        )}
      </div>

      {/* Nav items */}
      <nav style={{ flex: 1, padding: "var(--ha-space-2) 0", overflowY: "auto" }}>
        {NAV_ITEMS.map((item) => {
          const active = location.pathname === item.path ||
            (item.path !== "/" && location.pathname.startsWith(item.path));
          return (
            <button
              key={item.id}
              onClick={() => navigate(item.path)}
              title={collapsed ? item.label : undefined}
              aria-label={item.label}
              aria-current={active ? "page" : undefined}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "var(--ha-space-3)",
                width: "100%",
                padding: "var(--ha-space-2) var(--ha-space-4)",
                background: active
                  ? "color-mix(in srgb, var(--primary-color) 12%, transparent)"
                  : "transparent",
                color: active ? "var(--primary-color)" : "var(--secondary-text-color)",
                border: "none",
                cursor: "pointer",
                fontSize: "var(--ha-font-size-m)",
                fontFamily: "var(--ha-font-family-body)",
                textAlign: "left",
                borderRadius: "var(--ha-border-radius-md)",
                margin: "1px var(--ha-space-2)",
                transition: "background 0.15s, color 0.15s",
              }}
            >
              <span style={{ flexShrink: 0, display: "flex" }}>{item.icon}</span>
              {!collapsed && (
                <span style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {item.label}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed((c) => !c)}
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: collapsed ? "center" : "flex-end",
          padding: "var(--ha-space-3) var(--ha-space-4)",
          background: "transparent",
          border: "none",
          borderTop: "1px solid var(--divider-color)",
          color: "var(--secondary-text-color)",
          cursor: "pointer",
          width: "100%",
        }}
      >
        <ChevronIcon collapsed={collapsed} />
      </button>
    </aside>
  );
}

// ── SVG Icons ──────────────────────────────────────────────────────────────

function GridIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" />
    </svg>
  );
}

function MapIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6" />
      <line x1="8" y1="2" x2="8" y2="18" /><line x1="16" y1="6" x2="16" y2="22" />
    </svg>
  );
}

function VideoIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polygon points="23 7 16 12 23 17 23 7" />
      <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
    </svg>
  );
}

function DeviceIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="2" y="3" width="20" height="14" rx="2" /><line x1="8" y1="21" x2="16" y2="21" />
      <line x1="12" y1="17" x2="12" y2="21" />
    </svg>
  );
}

function PtzIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
    </svg>
  );
}

function LogIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" /><polyline points="10 9 9 9 8 9" />
    </svg>
  );
}

function SettingsIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );
}

function RadarIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--uav-color-alert)" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <circle cx="12" cy="12" r="6" />
      <circle cx="12" cy="12" r="2" fill="var(--uav-color-alert)" />
      <line x1="12" y1="2" x2="12" y2="6" />
      <line x1="12" y1="18" x2="12" y2="22" />
      <line x1="2" y1="12" x2="6" y2="12" />
      <line x1="18" y1="12" x2="22" y2="12" />
    </svg>
  );
}

function ChevronIcon({ collapsed }: { collapsed: boolean }) {
  return (
    <svg
      width="16" height="16" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2"
      style={{ transform: collapsed ? "rotate(180deg)" : "none", transition: "transform 0.2s" }}
    >
      <polyline points="15 18 9 12 15 6" />
    </svg>
  );
}
