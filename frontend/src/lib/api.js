// Thin API client. In dev, Vite proxies /api to the backend (see vite.config).
// In production set VITE_API_BASE to the backend origin at build time.
const BASE = import.meta.env.VITE_API_BASE || "";

export async function getHealth() {
  const res = await fetch(`${BASE}/api/health`);
  if (!res.ok) throw new Error(`Health check failed (${res.status})`);
  return res.json();
}

export async function analyze(wavBlob, targetWord, errorThreshold) {
  const form = new FormData();
  form.append("audio", wavBlob, "recording.wav");
  form.append("target_word", targetWord);
  if (errorThreshold != null) form.append("error_threshold", String(errorThreshold));

  const res = await fetch(`${BASE}/api/analyze`, { method: "POST", body: form });
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json();
}
