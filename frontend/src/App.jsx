import { useEffect, useRef, useState } from "react";
import { analyze, getHealth } from "./lib/api.js";
import { Recorder, toWav16k } from "./lib/audio.js";
import WaveformChart from "./components/WaveformChart.jsx";
import PhonemeList from "./components/PhonemeList.jsx";
import ScoreRing from "./components/ScoreRing.jsx";
import Logo from "./components/Logo.jsx";
import ThemeToggle, { useTheme } from "./components/ThemeToggle.jsx";
import ThresholdSlider, { DEFAULT_THRESHOLD } from "./components/ThresholdSlider.jsx";

const SUGGESTED = ["hello", "water", "yesterday", "computer", "beautiful", "seven", "purple", "animal"];

export default function App() {
  const [word, setWord] = useState("hello");
  const [status, setStatus] = useState("idle"); // idle | recording | processing
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [health, setHealth] = useState(null);
  const [audioUrl, setAudioUrl] = useState("");
  const [threshold, setThreshold] = useState(DEFAULT_THRESHOLD);
  const [theme, setTheme] = useTheme();

  const recorderRef = useRef(null);

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealth({ status: "down" }));
  }, []);

  async function submit(wavBlob) {
    setStatus("processing");
    setError("");
    try {
      if (audioUrl) URL.revokeObjectURL(audioUrl);
      setAudioUrl(URL.createObjectURL(wavBlob));
      const data = await analyze(wavBlob, word.trim(), threshold);
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
    if (!word.trim()) return setError("Enter a word to practise first.");

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
    if (!word.trim()) return setError("Enter a word to practise first.");
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
          <ThemeToggle theme={theme} onChange={setTheme} />
        </div>
      </header>

      <main className="container">
        <section className="card prompt-card">
          <label className="field-label" htmlFor="word">Word to practise</label>
          <input
            id="word"
            className="word-input"
            value={word}
            onChange={(e) => setWord(e.target.value)}
            placeholder="Type any word…"
            autoComplete="off"
            spellCheck="false"
          />
          <div className="chips">
            {SUGGESTED.map((w) => (
              <button
                key={w}
                className={`chip ${w === word ? "active" : ""}`}
                onClick={() => setWord(w)}
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

          {recording && <p className="hint pulse">Recording… say “{word}”, then press stop.</p>}
          {busy && <p className="hint">Aligning phonemes and scoring… first run may take a moment.</p>}
          {error && <p className="error">{error}</p>}
        </section>

        {result && (
          <section className="card result-card">
            <div className="result-head">
              <ScoreRing
                accuracy={result.accuracy}
                nErrors={result.n_errors}
                nPhonemes={result.n_phonemes}
              />
              <div className="result-meta">
                <h2>“{result.target_word}”</h2>
                <p className="muted">
                  {result.n_phonemes} phonemes · {result.n_errors} flagged ·{" "}
                  {result.duration_sec}s · threshold {result.error_threshold}
                </p>
                {audioUrl && <audio className="player" controls src={audioUrl} />}
              </div>
            </div>

            <WaveformChart
              waveform={result.waveform}
              rate={result.waveform_rate}
              phonemes={result.phonemes}
              duration={result.duration_sec}
            />

            <h3 className="section-title">Phoneme breakdown</h3>
            <PhonemeList phonemes={result.phonemes} />
          </section>
        )}

        {!result && !busy && (
          <section className="card empty-card">
            <p>
              Pick a word, tap <strong>Record</strong>, and say it clearly. Clario aligns your
              speech to the word’s phonemes and highlights any sounds that came out unclear.
            </p>
          </section>
        )}
      </main>

      <footer className="footer">
        <span>Clario · Speech clarity coach</span>
      </footer>
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
    : `Ready · ${health.device} · ${health.normalization}`;
  return (
    <div className={`health ${cls}`} title={title}>
      <span className="health-dot" />
      {!up ? "offline" : warn ? "degraded" : "ready"}
    </div>
  );
}
