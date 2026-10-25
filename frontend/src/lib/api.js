// Thin API client. In dev, Vite proxies /api to the backend (see vite.config).
// In production set VITE_API_BASE to the backend origin at build time.
const BASE = import.meta.env.VITE_API_BASE || "";
const TOKEN_KEY = "clario-token";

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable — stay signed in for this tab only */
  }
}

// Fired when the server rejects our token, so the app can drop to signed-out.
export const AUTH_EXPIRED_EVENT = "clario-auth-expired";

async function request(path, { method = "GET", body, json, raw = false } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  }

  const res = await fetch(`${BASE}${path}`, { method, headers, body });
  if (!res.ok) {
    if (res.status === 401 && token) {
      setToken(null);
      window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
    }
    let detail = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      if (typeof data?.detail === "string") detail = data.detail;
      else if (Array.isArray(data?.detail)) detail = data.detail.map((d) => d.msg).join("; ");
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (raw) return res;
  return res.status === 204 ? null : res.json();
}

export async function getHealth() {
  return request("/api/health");
}

export async function analyze(wavBlob, targetText, errorThreshold, mode = "word") {
  const form = new FormData();
  form.append("audio", wavBlob, "recording.wav");
  form.append("target_word", targetText);
  form.append("mode", mode);
  if (errorThreshold != null) form.append("error_threshold", String(errorThreshold));
  return request("/api/analyze", { method: "POST", body: form });
}

// --- accounts ---------------------------------------------------------------
export const register = (username, password) =>
  request("/api/auth/register", { method: "POST", json: { username, password } });

export const login = (username, password) =>
  request("/api/auth/login", { method: "POST", json: { username, password } });

export const getMe = () => request("/api/auth/me");

// --- history ----------------------------------------------------------------
export function listHistory({ limit = 20, offset = 0, mode } = {}) {
  const q = new URLSearchParams({ limit, offset });
  if (mode) q.set("mode", mode);
  return request(`/api/history?${q}`);
}

export const getAttempt = (id) => request(`/api/history/${id}`);

export const deleteAttempt = (id) => request(`/api/history/${id}`, { method: "DELETE" });

// <audio src> can't send the auth header, so fetch the recording as a blob URL.
export async function getAttemptAudioUrl(id) {
  const res = await request(`/api/history/${id}/audio`, { raw: true });
  return URL.createObjectURL(await res.blob());
}
