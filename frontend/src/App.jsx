import { useEffect, useRef, useState } from "react";
import { analyze, AUTH_EXPIRED_EVENT, getHealth, getMe, getToken, setToken } from "./lib/api.js";
import { Recorder, toWav16k } from "./lib/audio.js";
import ResultView from "./components/ResultView.jsx";
import HistoryView from "./components/HistoryView.jsx";
import AuthDialog from "./components/AuthDialog.jsx";
import Logo from "./components/Logo.jsx";
import ThemeToggle, { useTheme } from "./components/ThemeToggle.jsx";
import ThresholdSlider, { DEFAULT_THRESHOLD } from "./components/ThresholdSlider.jsx";

const SUGGESTED = {
  word: ["hello", "water", "yesterday", "computer", "beautiful", "seven", "purple", "animal"],
  sentence: [
    "The quick brown fox jumps over the lazy dog",
    "She sells seashells by the seashore",
    "I would like a glass of water",
    "Please call me tomorrow morning",
    "The weather is beautiful today",
  ],
};

const MODE_COPY = {
  word: { label: "Word to practise", placeholder: "Type any word…", noun: "word" },
  sentence: { label: "Sentence to practise", placeholder: "Type a sentence…", noun: "sentence" },
};

export default function App() {
  const [mode, setMode] = useState("word"); // word | sentence
  const [texts, setTexts] = useState({ word: "hello", sentence: SUGGESTED.sentence[1] });
  const [status, setStatus] = useState("idle"); // idle | recording | processing
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [health, setHealth] = useState(null);
  const [audioUrl, setAudioUrl] = useState("");
  const [threshold, setThreshold] = useState(DEFAULT_THRESHOLD);
  const [theme, setTheme] = useTheme();
  const [user, setUser] = useState(null);
  const [authOpen, setAuthOpen] = useState(false);
  const [view, setView] = useState("practice"); // practice | history

  const recorderRef = useRef(null);
  const text = texts[mode];
  const copy = MODE_COPY[mode];

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealth({ status: "down" }));
    if (getToken()) getMe().then(setUser).catch(() => setUser(null));

    const onExpired = () => {
      setUser(null);
      setView("practice");
    };
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired);
  }, []);

  function setText(value) {
    setTexts((t) => ({ ...t, [mode]: value }));
  }

  function switchMode(next) {
    if (next === mode || status !== "idle") return;
    setMode(next);
    setResult(null);
    setError("");
  }

  function handleAuthed({ token, user }) {
    setToken(token);
    setUser(user);
    setAuthOpen(false);
  }

  function signOut() {
    setToken(null);
    setUser(null);
    setView("practice");
  }

  async function submit(wavBlob) {
    setStatus("processing");
    setError("");
    try {
      if (audioUrl) URL.revokeObjectURL(audioUrl);
      setAudioUrl(URL.createObjectURL(wavBlob));
      const data = await analyze(wavBlob, text.trim(), threshold, mode);
      setResult(data);
    } catch (e) {
      setError(e.message || "Something went wrong.");
      setResult(null);
    } finally {
      setStatus("idle");
    }
  }

  async function handleRecord() {
    setError("");
    if (!text.trim()) return setError(`Enter a ${copy.noun} to practise first.`);

    if (status === "recording") {
      const blob = await recorderRef.current.stop();
      try {
        const wav = await toWav16k(blob);
        await submit(wav);
      } catch (e) {
        setStatus("idle");
        setError("Could not process the recording: " + e.message);
      }
      return;
    }

    try {
      recorderRef.current = new Recorder();
      await recorderRef.current.start();
      setStatus("recording");
      setResult(null);
    } catch (e) {
      setError("Microphone access denied or unavailable.");
    }
  }

  async function handleUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!text.trim()) return setError(`Enter a ${copy.noun} to practise first.`);
    try {
      const wav = await toWav16k(file);
      await submit(wav);
    } catch (err) {
      setError("Could not read that audio file: " + err.message);
    }
    e.target.value = "";
  }

  const busy = status === "processing";
  const recording = status === "recording";
  const historyAvailable = health?.history_enabled;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <Logo size={34} />
          <div>
            <h1>Clario</h1>
            <p className="tagline">Speech clarity coach</p>
          </div>
        </div>
        <div className="topbar-actions">
          <HealthDot health={health} />
          {historyAvailable &&
            (user ? (
              <>
                <button
                  type="button"
                  className={`nav-btn ${view === "history" ? "active" : ""}`}
                  onClick={() => setView(view === "history" ? "practice" : "history")}
                  disabled={status !== "idle"}
                >
                  {view === "history" ? "Practise" : "History"}
                </button>
                <button type="button" className="nav-btn" onClick={signOut} title="Sign out">
                  {user.username} · Sign out
                </button>
              </>
            ) : (
              <button type="button" className="nav-btn" onClick={() => setAuthOpen(true)}>
                Sign in
              </button>
            ))}
          <ThemeToggle theme={theme} onChange={setTheme} />
        </div>
      </header>

      <main className="container">
        {view === "history" && user ? (
          <HistoryView />
        ) : (
          <>
            <section className="card prompt-card">
              <div className="segmented mode-toggle" role="tablist" aria-label="Practice mode">
                {["word", "sentence"].map((m) => (
                  <button
                    key={m}
                    type="button"
                    role="tab"
                    aria-selected={mode === m}
                    className={mode === m ? "active" : ""}
                    onClick={() => switchMode(m)}
                    disabled={status !== "idle"}
                  >
                    {m === "word" ? "Word check" : "Sentence check"}
                  </button>
                ))}
              </div>

              <label className="field-label" htmlFor="target">{copy.label}</label>
              {mode === "word" ? (
                <input
                  id="target"
                  className="word-input"
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder={copy.placeholder}
                  autoComplete="off"
                  spellCheck="false"
                />
              ) : (
                <textarea
                  id="target"
                  className="word-input sentence-input"
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder={copy.placeholder}
                  rows={2}
                  spellCheck="false"
                />
              )}
              <div className="chips">
                {SUGGESTED[mode].map((w) => (
                  <button
                    key={w}
                    className={`chip ${w === text ? "active" : ""}`}
                    onClick={() => setText(w)}
                    type="button"
                  >
                    {w}
                  </button>
                ))}
              </div>

              <ThresholdSlider value={threshold} onChange={setThreshold} />

              <div className="actions">
                <button
                  className={`record-btn ${recording ? "recording" : ""}`}
                  onClick={handleRecord}
                  disabled={busy}
                  type="button"
                >
                  {recording ? "◼ Stop & analyse" : busy ? "Analysing…" : "🎙 Record"}
                </button>

                <label className="upload-btn">
                  ⤴ Upload audio
                  <input type="file" accept="audio/*" onChange={handleUpload} disabled={busy} hidden />
                </label>
              </div>

              {recording && <p className="hint pulse">Recording… say “{text}”, then press stop.</p>}
              {busy && <p className="hint">Aligning phonemes and scoring… first run may take a moment.</p>}
              {error && <p className="error">{error}</p>}
              {historyAvailable && !user && (
                <p className="hint small">
                  <button type="button" className="link-btn" onClick={() => setAuthOpen(true)}>
                    Sign in
                  </button>{" "}
                  to keep a history of your attempts.
                </p>
              )}
            </section>

            {result && (
              <ResultView result={result} audioUrl={audioUrl}>
                {result.attempt_id && <p className="saved-note">✓ Saved to your history</p>}
              </ResultView>
            )}

            {!result && !busy && (
              <section className="card empty-card">
                <p>
                  {mode === "word" ? (
                    <>
                      Pick a word, tap <strong>Record</strong>, and say it clearly. Clario aligns
                      your speech to the word’s phonemes and highlights any sounds that came out
                      unclear.
                    </>
                  ) : (
                    <>
                      Type a sentence, tap <strong>Record</strong>, and read it at a natural pace.
                      Clario scores every word, tells you how many you got right, and lets you
                      drill into the sounds of each one.
                    </>
                  )}
                </p>
              </section>
            )}
          </>
        )}
      </main>

      <footer className="footer">
        <span>Clario · Speech clarity coach</span>
      </footer>

      {authOpen && <AuthDialog onAuthed={handleAuthed} onClose={() => setAuthOpen(false)} />}
    </div>
  );
}

function HealthDot({ health }) {
  if (!health) return null;
  const up = health.status === "ok";
  const warn = up && (!health.espeak_available || !health.model_loaded);
  const cls = !up ? "down" : warn ? "warn" : "up";
  const title = !up
    ? "Backend unreachable"
    : warn
    ? `Degraded: espeak=${health.espeak_available}, model=${health.model_loaded}`
    : `Ready · ${health.device} · ${health.normalization}` +
      (health.history_enabled ? ` · db ${health.db_connected ? "connected" : "unreachable"}` : "");
  return (
    <div className={`health ${cls}`} title={title}>
      <span className="health-dot" />
      {!up ? "offline" : warn ? "degraded" : "ready"}
    </div>
  );
}
