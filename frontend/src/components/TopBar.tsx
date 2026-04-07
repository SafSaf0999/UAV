/**
 * Top bar — system name, WS connection status, user avatar, logout button.
 */

import React from "react";
import { useNavigate } from "react-router-dom";
import { clearToken, getDisplayName, getUsername } from "../utils/auth";

interface TopBarProps {
  wsConnected: boolean;
}

export function TopBar({ wsConnected }: TopBarProps) {
  const navigate = useNavigate();
  const displayName = getDisplayName() ?? getUsername() ?? "User";
  const initials = displayName
    .split(" ")
    .map((w) => w[0]?.toUpperCase() ?? "")
    .slice(0, 2)
    .join("");

  const handleLogout = async () => {
    try {
      const token = localStorage.getItem("uav_access_token");
      if (token) {
        await fetch("/auth/logout", {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        });
      }
    } catch {
      // ignore
    }
    clearToken();
    navigate("/login", { replace: true });
  };

  return (
    <header
      style={{
        height: "var(--topbar-height)",
        background: "var(--card-background-color)",
        borderBottom: "1px solid var(--divider-color)",
        display: "flex",
        alignItems: "center",
        padding: "0 var(--ha-space-6)",
        gap: "var(--ha-space-4)",
        position: "sticky",
        top: 0,
        zIndex: 99,
      }}
    >
      {/* System name */}
      <span style={{
        flex: 1,
        fontWeight: "var(--ha-font-weight-bold)" as any,
        fontSize: "var(--ha-font-size-l)",
        color: "var(--primary-text-color)",
        letterSpacing: "0.5px",
      }}>
        Anti-UAV Control Center
      </span>

      {/* WS connection status */}
      <div
        style={{ display: "flex", alignItems: "center", gap: "var(--ha-space-2)" }}
        title={wsConnected ? "Connected" : "Disconnected"}
        aria-label={wsConnected ? "System connected" : "System disconnected"}
      >
        <span style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: wsConnected ? "var(--uav-color-online)" : "var(--uav-color-offline)",
          display: "inline-block",
        }} />
        <span style={{ fontSize: "var(--ha-font-size-s)", color: "var(--secondary-text-color)" }}>
          {wsConnected ? "Connected" : "Disconnected"}
        </span>
      </div>

      {/* User avatar */}
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: "50%",
          background: "var(--primary-color)",
          color: "#fff",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: "var(--ha-font-size-s)",
          fontWeight: "var(--ha-font-weight-bold)" as any,
          flexShrink: 0,
        }}
        title={displayName}
        aria-label={`Logged in as ${displayName}`}
      >
        {initials || "U"}
      </div>

      {/* Logout */}
      <button
        onClick={handleLogout}
        aria-label="Sign out"
        style={{
          background: "transparent",
          border: "1px solid var(--divider-color)",
          borderRadius: "var(--ha-border-radius-md)",
          color: "var(--secondary-text-color)",
          cursor: "pointer",
          fontSize: "var(--ha-font-size-s)",
          padding: "var(--ha-space-1) var(--ha-space-3)",
          fontFamily: "var(--ha-font-family-body)",
        }}
      >
        Sign out
      </button>
    </header>
  );
}
