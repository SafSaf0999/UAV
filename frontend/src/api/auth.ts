/**
 * Auth API — user management and audit log endpoints.
 * All calls use authFetch which attaches Bearer token and redirects on 401.
 */

import { authFetch } from "../utils/auth";

export interface UserRecord {
  username: string;
  display_name: string;
  role: "admin" | "viewer";
  created_at: string;
  last_login: string | null;
  active: number;
}

export interface AuditEntry {
  username: string;
  display_name: string;
  action: string;
  device_id: string | null;
  payload: string | null;
  timestamp: string;
}

export interface InviteResponse {
  token: string;
  role: string;
  expires_at: string;
}

export async function listUsers(): Promise<UserRecord[]> {
  const resp = await authFetch("/auth/users");
  if (!resp.ok) throw new Error("Failed to list users");
  return resp.json();
}

export async function deactivateUser(username: string): Promise<void> {
  const resp = await authFetch(`/auth/users/${username}`, { method: "DELETE" });
  if (!resp.ok) throw new Error("Failed to deactivate user");
}

export async function createInvite(
  role: "admin" | "viewer",
  expiryHours: number = 48
): Promise<InviteResponse> {
  const resp = await authFetch("/auth/invite", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role, expiry_hours: expiryHours }),
  });
  if (!resp.ok) throw new Error("Failed to create invite");
  return resp.json();
}

export async function getAuditLog(
  limit: number = 100,
  username?: string,
  deviceId?: string
): Promise<AuditEntry[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (username) params.set("username", username);
  if (deviceId) params.set("device_id", deviceId);
  const resp = await authFetch(`/auth/audit?${params}`);
  if (!resp.ok) throw new Error("Failed to fetch audit log");
  return resp.json();
}

// ---------------------------------------------------------------------------
// Tokens
// ---------------------------------------------------------------------------

export interface TokenRecord {
  token: string;
  role: string;
  created_by: string;
  created_at: string;
  expires_at: string;
  status: "pending" | "used" | "expired";
  used_by: string | null;
}

export async function listTokens(): Promise<TokenRecord[]> {
  const resp = await authFetch("/auth/tokens");
  if (!resp.ok) throw new Error("Failed to list tokens");
  return resp.json();
}

export async function revokeToken(token: string): Promise<void> {
  const resp = await authFetch(`/auth/tokens/${token}`, { method: "DELETE" });
  if (!resp.ok) throw new Error("Failed to revoke token");
}

// ---------------------------------------------------------------------------
// Sessions
// ---------------------------------------------------------------------------

export interface SessionRecord {
  jti: string;
  username: string;
  display_name: string;
  login_time: string;
  last_seen: string;
  user_agent: string | null;
  expires_at: string;
}

export async function listSessions(): Promise<SessionRecord[]> {
  const resp = await authFetch("/auth/sessions");
  if (!resp.ok) throw new Error("Failed to list sessions");
  return resp.json();
}

export async function revokeSession(jti: string): Promise<void> {
  const resp = await authFetch(`/auth/sessions/${jti}`, { method: "DELETE" });
  if (!resp.ok) throw new Error("Failed to revoke session");
}

// ---------------------------------------------------------------------------
// Webhooks
// ---------------------------------------------------------------------------

export interface WebhookRecord {
  id: number;
  url: string;
  events: string;
  secret: string;
  enabled: number;
}

export async function listWebhooks(): Promise<WebhookRecord[]> {
  const resp = await authFetch("/auth/webhooks");
  if (!resp.ok) throw new Error("Failed to list webhooks");
  return resp.json();
}

export async function createWebhook(
  url: string,
  events: string[],
  secret: string
): Promise<WebhookRecord> {
  const resp = await authFetch("/auth/webhooks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, events: events.join(","), secret }),
  });
  if (!resp.ok) throw new Error("Failed to create webhook");
  return resp.json();
}

export async function updateWebhook(
  id: number,
  data: Partial<WebhookRecord>
): Promise<void> {
  const resp = await authFetch(`/auth/webhooks/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!resp.ok) throw new Error("Failed to update webhook");
}

export async function deleteWebhook(id: number): Promise<void> {
  const resp = await authFetch(`/auth/webhooks/${id}`, { method: "DELETE" });
  if (!resp.ok) throw new Error("Failed to delete webhook");
}

export async function testWebhook(id: number): Promise<{ status_code: number | null; error?: string }> {
  const resp = await authFetch(`/auth/webhooks/${id}/test`, { method: "POST" });
  if (!resp.ok) throw new Error("Failed to test webhook");
  return resp.json();
}

// ---------------------------------------------------------------------------
// Thresholds
// ---------------------------------------------------------------------------

export interface ThresholdConfig {
  device_id: string;
  min_confidence: number;
  consecutive_frames: number;
  alert_classes: string[];
}

export async function getThresholds(device_id: string): Promise<ThresholdConfig> {
  const resp = await authFetch(`/api/devices/${device_id}/thresholds`);
  if (!resp.ok) throw new Error("Failed to get thresholds");
  return resp.json();
}

export async function updateThresholds(
  device_id: string,
  config: Partial<ThresholdConfig>
): Promise<ThresholdConfig> {
  const resp = await authFetch(`/api/devices/${device_id}/thresholds`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  if (!resp.ok) throw new Error("Failed to update thresholds");
  return resp.json();
}
