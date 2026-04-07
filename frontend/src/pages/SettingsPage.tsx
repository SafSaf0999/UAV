/**
 * Settings page — card-based layout with theme toggle, user management,
 * and audit log (admin only).
 *
 * Requirements: v2-1.13, v2-1.14, v2-1.16–1.19, v2-2.8, v2-2.9
 */

import React, { useEffect, useState } from "react";
import { Card } from "../components/ui/Card";
import { StatChip } from "../components/ui/StatChip";
import { getUserRole } from "../utils/auth";
import {
  listUsers, deactivateUser, createInvite, getAuditLog,
  type UserRecord, type AuditEntry, type InviteResponse,
} from "../api/auth";

// ---------------------------------------------------------------------------
// Theme toggle
// ---------------------------------------------------------------------------

function ThemeCard() {
  const [theme, setTheme] = useState<"dark" | "light">(() => {
    return (localStorage.getItem("uav_theme") as "dark" | "light") ?? "dark";
  });

  const toggle = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    localStorage.setItem("uav_theme", next);
    document.documentElement.setAttribute("data-theme", next);
  };

  return (
    <Card>
      <SectionTitle>Appearance</SectionTitle>
      <div style={{ display: "flex", alignItems: "center", gap: "var(--ha-space-4)" }}>
        <span style={{ fontSize: "var(--ha-font-size-m)" }}>Theme</span>
        <button onClick={toggle} style={toggleBtnStyle} aria-label="Toggle theme">
          {theme === "dark" ? "☀ Light" : "🌙 Dark"}
        </button>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Users card (admin only)
// ---------------------------------------------------------------------------

function UsersCard() {
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [inviteRole, setInviteRole] = useState<"viewer" | "admin">("viewer");
  const [inviteExpiry, setInviteExpiry] = useState(48);
  const [generatedInvite, setGeneratedInvite] = useState<InviteResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    listUsers().then(setUsers).catch(() => {});
  }, []);

  const handleDeactivate = async (username: string) => {
    if (!confirm(`Deactivate ${username}?`)) return;
    await deactivateUser(username);
    setUsers((prev) => prev.map((u) => u.username === username ? { ...u, active: 0 } : u));
  };

  const handleGenerateInvite = async () => {
    setLoading(true);
    try {
      const inv = await createInvite(inviteRole, inviteExpiry);
      setGeneratedInvite(inv);
    } finally {
      setLoading(false);
    }
  };

  const copyToken = () => {
    if (generatedInvite) {
      navigator.clipboard.writeText(generatedInvite.token);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const shareLink = () => {
    if (generatedInvite) {
      const url = `${window.location.origin}/register?token=${generatedInvite.token}`;
      navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <Card>
      <SectionTitle>Users</SectionTitle>

      {/* User list */}
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "var(--ha-font-size-s)", marginBottom: "var(--ha-space-4)" }}>
        <thead>
          <tr style={{ borderBottom: "1px solid var(--divider-color)" }}>
            {["Display Name", "Username", "Role", "Created", "Last Login", ""].map((h) => (
              <th key={h} style={thStyle}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.username} style={{ borderBottom: "1px solid var(--divider-color)", opacity: u.active ? 1 : 0.4 }}>
              <td style={tdStyle}>{u.display_name}</td>
              <td style={{ ...tdStyle, fontFamily: "var(--ha-font-family-code)" }}>{u.username}</td>
              <td style={tdStyle}>
                <StatChip label={u.role} color={u.role === "admin" ? "var(--primary-color)" : "var(--secondary-text-color)"} />
              </td>
              <td style={tdStyle}>{new Date(u.created_at).toLocaleDateString()}</td>
              <td style={tdStyle}>{u.last_login ? new Date(u.last_login).toLocaleDateString() : "—"}</td>
              <td style={tdStyle}>
                {u.active ? (
                  <button onClick={() => handleDeactivate(u.username)} style={dangerBtnStyle}>Deactivate</button>
                ) : (
                  <span style={{ fontSize: "var(--ha-font-size-xs)", color: "var(--disabled-text-color)" }}>Inactive</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Generate invite */}
      <div style={{ borderTop: "1px solid var(--divider-color)", paddingTop: "var(--ha-space-3)" }}>
        <div style={{ fontSize: "var(--ha-font-size-s)", color: "var(--secondary-text-color)", marginBottom: "var(--ha-space-2)" }}>
          Generate Invite Token
        </div>
        <div style={{ display: "flex", gap: "var(--ha-space-2)", alignItems: "center", flexWrap: "wrap" }}>
          <select value={inviteRole} onChange={(e) => setInviteRole(e.target.value as any)} style={selectStyle}>
            <option value="viewer">Viewer</option>
            <option value="admin">Admin</option>
          </select>
          <select value={inviteExpiry} onChange={(e) => setInviteExpiry(Number(e.target.value))} style={selectStyle}>
            <option value={24}>24h</option>
            <option value={48}>48h</option>
            <option value={168}>7 days</option>
            <option value={720}>30 days</option>
          </select>
          <button onClick={handleGenerateInvite} style={btnStyle} disabled={loading}>
            {loading ? "Generating…" : "Generate"}
          </button>
        </div>
        {generatedInvite && (
          <div style={{ marginTop: "var(--ha-space-3)", display: "flex", gap: "var(--ha-space-2)", alignItems: "center", flexWrap: "wrap" }}>
            <code style={{ background: "var(--secondary-background-color)", padding: "var(--ha-space-1) var(--ha-space-2)", borderRadius: "var(--ha-border-radius-sm)", fontSize: "var(--ha-font-size-m)", letterSpacing: "0.1em" }}>
              {generatedInvite.token}
            </code>
            <button onClick={copyToken} style={btnStyle}>{copied ? "Copied!" : "Copy Token"}</button>
            <button onClick={shareLink} style={btnStyle}>Copy Link</button>
            <span style={{ fontSize: "var(--ha-font-size-xs)", color: "var(--secondary-text-color)" }}>
              Expires: {new Date(generatedInvite.expires_at).toLocaleString()}
            </span>
          </div>
        )}
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Audit log card (admin only)
// ---------------------------------------------------------------------------

function AuditLogCard() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [filterUser, setFilterUser] = useState("");
  const [filterDevice, setFilterDevice] = useState("");

  useEffect(() => {
    getAuditLog(100, filterUser || undefined, filterDevice || undefined)
      .then(setEntries)
      .catch(() => {});
  }, [filterUser, filterDevice]);

  return (
    <Card>
      <SectionTitle>Audit Log</SectionTitle>
      <div style={{ display: "flex", gap: "var(--ha-space-2)", marginBottom: "var(--ha-space-3)", flexWrap: "wrap" }}>
        <input
          placeholder="Filter by user"
          value={filterUser}
          onChange={(e) => setFilterUser(e.target.value)}
          style={inputStyle}
        />
        <input
          placeholder="Filter by device"
          value={filterDevice}
          onChange={(e) => setFilterDevice(e.target.value)}
          style={inputStyle}
        />
      </div>
      <div style={{ maxHeight: 300, overflowY: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "var(--ha-font-size-xs)" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--divider-color)" }}>
              {["Time", "User", "Action", "Device"].map((h) => (
                <th key={h} style={thStyle}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {entries.map((e, i) => (
              <tr key={i} style={{ borderBottom: "1px solid var(--divider-color)" }}>
                <td style={tdStyle}>{new Date(e.timestamp).toLocaleTimeString()}</td>
                <td style={tdStyle}>{e.display_name} <span style={{ color: "var(--secondary-text-color)" }}>({e.username})</span></td>
                <td style={{ ...tdStyle, fontFamily: "var(--ha-font-family-code)" }}>{e.action}</td>
                <td style={{ ...tdStyle, fontFamily: "var(--ha-font-family-code)" }}>{e.device_id ?? "—"}</td>
              </tr>
            ))}
            {entries.length === 0 && (
              <tr><td colSpan={4} style={{ ...tdStyle, color: "var(--secondary-text-color)", textAlign: "center" }}>No audit entries.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function SettingsPage() {
  const role = getUserRole();
  const isAdmin = role === "admin";

  return (
    <div style={{ padding: "var(--ha-space-6)", display: "flex", flexDirection: "column", gap: "var(--ha-space-4)" }}>
      <ThemeCard />
      {isAdmin && <UsersCard />}
      {isAdmin && <AuditLogCard />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared styles
// ---------------------------------------------------------------------------

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontSize: "var(--ha-font-size-s)", fontWeight: "var(--ha-font-weight-medium)" as any, color: "var(--secondary-text-color)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "var(--ha-space-3)" }}>
      {children}
    </div>
  );
}

const toggleBtnStyle: React.CSSProperties = {
  background: "var(--secondary-background-color)",
  border: "1px solid var(--divider-color)",
  borderRadius: "var(--ha-border-radius-pill)",
  color: "var(--primary-text-color)",
  cursor: "pointer",
  fontSize: "var(--ha-font-size-s)",
  padding: "var(--ha-space-1) var(--ha-space-4)",
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

const dangerBtnStyle: React.CSSProperties = {
  ...btnStyle,
  color: "var(--uav-color-alert)",
  borderColor: "color-mix(in srgb, var(--uav-color-alert) 30%, transparent)",
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

const thStyle: React.CSSProperties = {
  padding: "var(--ha-space-2) var(--ha-space-3)",
  textAlign: "left",
  color: "var(--secondary-text-color)",
  fontWeight: "normal",
  fontSize: "var(--ha-font-size-xs)",
};

const tdStyle: React.CSSProperties = {
  padding: "var(--ha-space-2) var(--ha-space-3)",
};
