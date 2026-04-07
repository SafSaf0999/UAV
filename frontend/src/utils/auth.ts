/**
 * Auth token helpers — store/retrieve JWT from localStorage.
 */

const TOKEN_KEY = "uav_access_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export function isTokenExpired(token: string): boolean {
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return payload.exp * 1000 < Date.now();
  } catch {
    return true;
  }
}

export function getUserRole(): string | null {
  const token = getToken();
  if (!token || isTokenExpired(token)) return null;
  try {
    return JSON.parse(atob(token.split(".")[1])).role ?? null;
  } catch {
    return null;
  }
}

export function getDisplayName(): string | null {
  const token = getToken();
  if (!token || isTokenExpired(token)) return null;
  try {
    return JSON.parse(atob(token.split(".")[1])).display_name ?? null;
  } catch {
    return null;
  }
}

export function getUsername(): string | null {
  const token = getToken();
  if (!token || isTokenExpired(token)) return null;
  try {
    return JSON.parse(atob(token.split(".")[1])).sub ?? null;
  } catch {
    return null;
  }
}

/** Attach Authorization header to fetch options if token exists. */
export function authHeaders(): Record<string, string> {
  const token = getToken();
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

/** Fetch wrapper that attaches auth header and redirects to /login on 401. */
export async function authFetch(
  input: RequestInfo,
  init: RequestInit = {}
): Promise<Response> {
  const headers = { ...(init.headers as Record<string, string> ?? {}), ...authHeaders() };
  const resp = await fetch(input, { ...init, headers });
  if (resp.status === 401) {
    clearToken();
    window.location.href = "/login";
  }
  return resp;
}
