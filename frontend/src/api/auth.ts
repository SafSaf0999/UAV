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
