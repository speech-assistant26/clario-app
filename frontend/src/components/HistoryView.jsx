import { useEffect, useState } from "react";
import { deleteAttempt, getAttempt, getAttemptAudioUrl, listHistory } from "../lib/api.js";
import ResultView from "./ResultView.jsx";

const PAGE = 20;

function pct(v) {
  return v == null ? "–" : `${Math.round(v * 100)}%`;
}

function band(v) {
  if (v == null) return "";
  return v >= 0.85 ? "ok" : v >= 0.6 ? "mid" : "err";
}

// The signed-in user's past attempts, newest first; tap one to re-open it.
export default function HistoryView() {
  const [mode, setMode] = useState(""); // "" = all
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(null); // { detail, audioUrl }

  async function load(offset = 0) {
    setLoading(true);
    setError("");
    try {
      const page = await listHistory({ limit: PAGE, offset, mode: mode || undefined });
      setItems((prev) => (offset ? [...prev, ...page.items] : page.items));
      setTotal(page.total);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(0);
  }, [mode]); // eslint-disable-line react-hooks/exhaustive-deps

  // Free the previous recording's blob URL whenever the open attempt changes.
  useEffect(() => () => open?.audioUrl && URL.revokeObjectURL(open.audioUrl), [open]);

  async function openAttempt(item) {
    setError("");
    try {
      const detail = await getAttempt(item.id);
      const audioUrl = detail.has_audio ? await getAttemptAudioUrl(item.id).catch(() => "") : "";
      setOpen({ detail, audioUrl });
    } catch (e) {
      setError(e.message);
    }
  }

  async function remove(id) {
    try {
      await deleteAttempt(id);
      setItems((prev) => prev.filter((i) => i.id !== id));
      setTotal((t) => t - 1);
      if (open?.detail.id === id) setOpen(null);
    } catch (e) {
      setError(e.message);
    }
  }

  if (open) {
    return (
      <>
        <button type="button" className="ghost-btn back-btn" onClick={() => setOpen(null)}>
          ← Back to history
        </button>
        <ResultView result={open.detail} audioUrl={open.audioUrl}>
          <p className="muted when">{new Date(open.detail.created_at).toLocaleString()}</p>
        </ResultView>
      </>
    );
  }

  return (
    <section className="card history-card">
      <div className="history-head">
        <h2>Your history</h2>
        <div className="segmented small">
          {[
            ["", "All"],
            ["word", "Words"],
            ["sentence", "Sentences"],
          ].map(([key, label]) => (
            <button
              key={key || "all"}
              type="button"
              className={mode === key ? "active" : ""}
              onClick={() => setMode(key)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {error && <p className="error">{error}</p>}
      {!loading && !items.length && !error && (
        <p className="muted">No attempts yet — practise a word or sentence and it will show up here.</p>
      )}

      <ul className="history-list">
        {items.map((it) => {
          const score = it.mode === "sentence" ? it.word_accuracy : it.accuracy;
          return (
            <li key={it.id} className="history-row">
              <button type="button" className="history-open" onClick={() => openAttempt(it)}>
                <span className={`history-score ${band(score)}`}>{pct(score)}</span>
                <span className="history-text">
                  <span className="history-target">{it.target_word}</span>
                  <span className="muted">
                    {it.mode === "sentence"
                      ? `${it.n_words_correct}/${it.n_words} words`
                      : `${it.n_phonemes - it.n_errors}/${it.n_phonemes} phonemes`}{" "}
                    · {new Date(it.created_at).toLocaleString()}
                    {it.has_audio && " · 🔊"}
                  </span>
                </span>
              </button>
              <ConfirmDelete onConfirm={() => remove(it.id)} />
            </li>
          );
        })}
      </ul>

      {loading && <p className="hint">Loading…</p>}
      {!loading && items.length < total && (
        <button type="button" className="ghost-btn more-btn" onClick={() => load(items.length)}>
          Load more ({total - items.length} left)
        </button>
      )}
    </section>
  );
}

// Two-step delete (no confirm() dialogs): first tap arms, second tap deletes.
function ConfirmDelete({ onConfirm }) {
  const [armed, setArmed] = useState(false);
  useEffect(() => {
    if (!armed) return;
    const t = setTimeout(() => setArmed(false), 3000);
    return () => clearTimeout(t);
  }, [armed]);
  return (
    <button
      type="button"
      className={`delete-btn ${armed ? "armed" : ""}`}
      onClick={() => (armed ? onConfirm() : setArmed(true))}
      aria-label="Delete attempt"
      title="Delete attempt"
    >
      {armed ? "Delete?" : "✕"}
    </button>
  );
}
