/**
 * Settings page — card-based layout with theme toggle, user management,
 * tokens, sessions, notifications (webhooks), thresholds, and audit log (admin only).
 *
 * Requirements: v2-1.13, v2-1.14, v2-1.16–1.19, v2-2.8, v2-2.9
 */

import React, { useEffect, useState } from "react";
import { Card } from "../components/ui/Card";
import { StatChip } from "../components/ui/StatChip";
import { getUserRole } from "../utils/auth";
import { useDevices } from "../api/websocket";
import {
  listUsers, deactivateUser, createInvite, getAuditLog,
  listTokens, revokeToken,
  listSessions, revokeSession,
  listWebhooks, createWebhook, updateWebhook, deleteWebhook, testWebhook,
  getThresholds, updateThresholds,
  type UserRecord, type AuditEntry, type InviteResponse,
  type TokenRecord, type SessionRecord, type WebhookRecord, type ThresholdConfig,
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
// Tokens card (admin only)
// ---------------------------------------------------------------------------

const TOKEN_STATUS_COLORS: Record<string, string> = {
  pending: "#3b82f6",
  used: "#22c55e",
  expired: "var(--secondary-text-color)",
};

function TokensCard() {
  const [tokens, setTokens] = useState<TokenRecord[]>([]);

  useEffect(() => {
    listTokens().then(setTokens).catch(() => {});
  }, []);

  const handleRevoke = async (token: string) => {
    await revokeToken(token).catch(() => {});
    setTokens((prev) => prev.filter((t) => t.token !== token));
  };

  const copyLink = (token: string) => {
    navigator.clipboard.writeText(`${window.location.origin}/register?token=${token}`);
  };

  return (
    <Card>
      <SectionTitle>Tokens</SectionTitle>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "var(--ha-font-size-s)" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--divider-color)" }}>
              {["Token", "Role", "Created By", "Created At", "Expires At", "Status", "Used By", ""].map((h) => (
                <th key={h} style={thStyle}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {tokens.map((t) => (
              <tr key={t.token} style={{ borderBottom: "1px solid var(--divider-color)" }}>
                <td style={{ ...tdStyle, fontFamily: "var(--ha-font-family-code)", maxWidth: 120, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{t.token}</td>
                <td style={tdStyle}>{t.role}</td>
                <td style={tdStyle}>{t.created_by}</td>
                <td style={tdStyle}>{new Date(t.created_at).toLocaleDateString()}</td>
                <td style={tdStyle}>{new Date(t.expires_at).toLocaleDateString()}</td>
                <td style={tdStyle}>
                  <span style={{ color: TOKEN_STATUS_COLORS[t.status] ?? "inherit", fontWeight: "bold" }}>{t.status}</span>
                </td>
                <td style={tdStyle}>{t.used_by ?? "—"}</td>
                <td style={{ ...tdStyle, display: "flex", gap: "var(--ha-space-1)" }}>
                  <button onClick={() => copyLink(t.token)} style={btnStyle}>Copy Link</button>
                  {t.status === "pending" && (
                    <button onClick={() => handleRevoke(t.token)} style={dangerBtnStyle}>Revoke</button>
                  )}
                </td>
              </tr>
            ))}
            {tokens.length === 0 && (
              <tr><td colSpan={8} style={{ ...tdStyle, color: "var(--secondary-text-color)", textAlign: "center" }}>No tokens.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Sessions card (admin only)
// ---------------------------------------------------------------------------

function SessionsCard() {
  const [sessions, setSessions] = useState<SessionRecord[]>([]);

  useEffect(() => {
    listSessions().then(setSessions).catch(() => {});
  }, []);

  const handleRevoke = async (jti: string) => {
    await revokeSession(jti).catch(() => {});
    setSessions((prev) => prev.filter((s) => s.jti !== jti));
  };

  return (
    <Card>
      <SectionTitle>Sessions</SectionTitle>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "var(--ha-font-size-s)" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--divider-color)" }}>
              {["Username", "Display Name", "Login Time", "Last Seen", "User Agent", ""].map((h) => (
                <th key={h} style={thStyle}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sessions.map((s) => (
              <tr key={s.jti} style={{ borderBottom: "1px solid var(--divider-color)" }}>
                <td style={{ ...tdStyle, fontFamily: "var(--ha-font-family-code)" }}>{s.username}</td>
                <td style={tdStyle}>{s.display_name}</td>
                <td style={tdStyle}>{new Date(s.login_time).toLocaleString()}</td>
                <td style={tdStyle}>{new Date(s.last_seen).toLocaleString()}</td>
                <td style={{ ...tdStyle, maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{s.user_agent ?? "—"}</td>
                <td style={tdStyle}>
                  <button onClick={() => handleRevoke(s.jti)} style={dangerBtnStyle}>Revoke</button>
                </td>
              </tr>
            ))}
            {sessions.length === 0 && (
              <tr><td colSpan={6} style={{ ...tdStyle, color: "var(--secondary-text-color)", textAlign: "center" }}>No active sessions.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Notifications (webhooks) card (admin only)
// ---------------------------------------------------------------------------

const WEBHOOK_EVENTS = ["detection_alert", "device_online", "device_offline"];

function NotificationsCard() {
  const [webhooks, setWebhooks] = useState<WebhookRecord[]>([]);
  const [newUrl, setNewUrl] = useState("");
  const [newEvents, setNewEvents] = useState<string[]>([]);
  const [newSecret, setNewSecret] = useState("");
  const [testResults, setTestResults] = useState<Record<number, string>>({});
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    listWebhooks().then(setWebhooks).catch(() => {});
  }, []);

  const handleAdd = async () => {
    if (!newUrl) return;
    setAdding(true);
    try {
      const wh = await createWebhook(newUrl, newEvents, newSecret);
      setWebhooks((prev) => [...prev, wh]);
      setNewUrl("");
      setNewEvents([]);
      setNewSecret("");
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (id: number) => {
    await deleteWebhook(id).catch(() => {});
    setWebhooks((prev) => prev.filter((w) => w.id !== id));
  };

  const handleToggle = async (wh: WebhookRecord) => {
    const enabled = wh.enabled ? 0 : 1;
    await updateWebhook(wh.id, { enabled }).catch(() => {});
    setWebhooks((prev) => prev.map((w) => w.id === wh.id ? { ...w, enabled } : w));
  };

  const handleTest = async (id: number) => {
    try {
      const result = await testWebhook(id);
      setTestResults((prev) => ({ ...prev, [id]: result.error ? `Error: ${result.error}` : `HTTP ${result.status_code}` }));
    } catch {
      setTestResults((prev) => ({ ...prev, [id]: "Failed" }));
    }
  };

  const toggleEvent = (ev: string) => {
    setNewEvents((prev) => prev.includes(ev) ? prev.filter((e) => e !== ev) : [...prev, ev]);
  };

  return (
    <Card>
      <SectionTitle>Notifications (Webhooks)</SectionTitle>
      <div style={{ overflowX: "auto", marginBottom: "var(--ha-space-4)" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "var(--ha-font-size-s)" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--divider-color)" }}>
              {["URL", "Events", "Enabled", ""].map((h) => (
                <th key={h} style={thStyle}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {webhooks.map((wh) => (
              <tr key={wh.id} style={{ borderBottom: "1px solid var(--divider-color)" }}>
                <td style={{ ...tdStyle, maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{wh.url}</td>
                <td style={{ ...tdStyle, fontSize: "var(--ha-font-size-xs)" }}>{wh.events}</td>
                <td style={tdStyle}>
                  <button onClick={() => handleToggle(wh)} style={{ ...btnStyle, color: wh.enabled ? "var(--uav-color-online)" : "var(--secondary-text-color)" }}>
                    {wh.enabled ? "On" : "Off"}
                  </button>
                </td>
                <td style={{ ...tdStyle, display: "flex", gap: "var(--ha-space-1)", alignItems: "center" }}>
                  <button onClick={() => handleTest(wh.id)} style={btnStyle}>Test</button>
                  {testResults[wh.id] && (
                    <span style={{ fontSize: "var(--ha-font-size-xs)", color: "var(--secondary-text-color)" }}>{testResults[wh.id]}</span>
                  )}
                  <button onClick={() => handleDelete(wh.id)} style={dangerBtnStyle}>Delete</button>
                </td>
              </tr>
            ))}
            {webhooks.length === 0 && (
              <tr><td colSpan={4} style={{ ...tdStyle, color: "var(--secondary-text-color)", textAlign: "center" }}>No webhooks configured.</td></tr>
            )}
          </tbody>
        </table>
      </div>
      <div style={{ borderTop: "1px solid var(--divider-color)", paddingTop: "var(--ha-space-3)" }}>
        <div style={{ fontSize: "var(--ha-font-size-s)", color: "var(--secondary-text-color)", marginBottom: "var(--ha-space-2)" }}>Add Webhook</div>
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--ha-space-2)" }}>
          <input placeholder="URL" value={newUrl} onChange={(e) => setNewUrl(e.target.value)} style={inputStyle} />
          <div style={{ display: "flex", gap: "var(--ha-space-3)", flexWrap: "wrap" }}>
            {WEBHOOK_EVENTS.map((ev) => (
              <label key={ev} style={{ display: "flex", alignItems: "center", gap: "var(--ha-space-1)", fontSize: "var(--ha-font-size-s)", cursor: "pointer" }}>
                <input type="checkbox" checked={newEvents.includes(ev)} onChange={() => toggleEvent(ev)} />
                {ev}
              </label>
            ))}
          </div>
          <input placeholder="Secret (optional)" value={newSecret} onChange={(e) => setNewSecret(e.target.value)} style={inputStyle} />
          <div>
            <button onClick={handleAdd} style={btnStyle} disabled={adding || !newUrl}>
              {adding ? "Adding…" : "Add Webhook"}
            </button>
          </div>
        </div>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Thresholds card (admin only)
// ---------------------------------------------------------------------------

const ALERT_CLASSES = ["drone", "bird", "person"];

function ThresholdsCard() {
  const devices = useDevices();
  const deviceIds = Object.keys(devices);
  const [selectedDevice, setSelectedDevice] = useState("");
  const [config, setConfig] = useState<ThresholdConfig | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!selectedDevice) return;
    getThresholds(selectedDevice).then(setConfig).catch(() => {});
  }, [selectedDevice]);

  const handleSave = async () => {
    if (!config || !selectedDevice) return;
    setSaving(true);
    try {
      const updated = await updateThresholds(selectedDevice, config);
      setConfig(updated);
    } finally {
      setSaving(false);
    }
  };

  const toggleClass = (cls: string) => {
    if (!config) return;
    const alert_classes = config.alert_classes.includes(cls)
      ? config.alert_classes.filter((c) => c !== cls)
      : [...config.alert_classes, cls];
    setConfig({ ...config, alert_classes });
  };

  return (
    <Card>
      <SectionTitle>Detection Thresholds</SectionTitle>
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--ha-space-3)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--ha-space-2)" }}>
          <label style={labelStyle}>Device:</label>
          <select value={selectedDevice} onChange={(e) => setSelectedDevice(e.target.value)} style={selectStyle}>
            <option value="">Select device…</option>
            {deviceIds.map((id) => <option key={id} value={id}>{id}</option>)}
          </select>
        </div>
        {config && (
          <>
            <div style={{ display: "flex", alignItems: "center", gap: "var(--ha-space-3)" }}>
              <label style={labelStyle}>Min Confidence:</label>
              <input
                type="range" min={0} max={1} step={0.01}
                value={config.min_confidence}
                onChange={(e) => setConfig({ ...config, min_confidence: Number(e.target.value) })}
                style={{ flex: 1 }}
              />
              <span style={{ fontSize: "var(--ha-font-size-s)", minWidth: 36 }}>{(config.min_confidence * 100).toFixed(0)}%</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "var(--ha-space-3)" }}>
              <label style={labelStyle}>Consecutive Frames:</label>
              <input
                type="number" min={1} max={60}
                value={config.consecutive_frames}
                onChange={(e) => setConfig({ ...config, consecutive_frames: Number(e.target.value) })}
                style={{ ...inputStyle, width: 80 }}
              />
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "var(--ha-space-3)", flexWrap: "wrap" }}>
              <label style={labelStyle}>Alert Classes:</label>
              {ALERT_CLASSES.map((cls) => (
                <label key={cls} style={{ display: "flex", alignItems: "center", gap: "var(--ha-space-1)", fontSize: "var(--ha-font-size-s)", cursor: "pointer" }}>
                  <input type="checkbox" checked={config.alert_classes.includes(cls)} onChange={() => toggleClass(cls)} />
                  {cls}
                </label>
              ))}
            </div>
            <div>
              <button onClick={handleSave} style={btnStyle} disabled={saving}>
                {saving ? "Saving…" : "Save"}
              </button>
            </div>
          </>
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
      {isAdmin && <TokensCard />}
      {isAdmin && <SessionsCard />}
      {isAdmin && <NotificationsCard />}
      {isAdmin && <ThresholdsCard />}
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

const labelStyle: React.CSSProperties = {
  fontSize: "var(--ha-font-size-s)",
  color: "var(--secondary-text-color)",
  minWidth: 140,
};

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
