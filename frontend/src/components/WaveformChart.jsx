import { useEffect, useRef } from "react";

// Canvas waveform with per-phoneme spans shaded red (error) / green (ok).
// Word mode labels each phoneme above its span; sentence mode (when `words`
// is given) labels words instead — phoneme labels would overlap — and
// outlines the currently selected word.
export default function WaveformChart({ waveform, rate, phonemes, duration, words, selectedWord }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !waveform?.length) return;

    const dpr = window.devicePixelRatio || 1;
    const cssW = canvas.clientWidth;
    const cssH = canvas.clientHeight;
    canvas.width = cssW * dpr;
    canvas.height = cssH * dpr;
    const ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, cssW, cssH);

    const mid = cssH / 2;
    const total = duration || waveform.length / rate;
    const xOf = (t) => (t / total) * cssW;

    // Phoneme span backgrounds.
    for (const p of phonemes) {
      const x0 = xOf(p.start);
      const x1 = xOf(p.end);
      ctx.fillStyle =
        p.verdict === "ERROR" ? "rgba(244,63,94,0.16)" : "rgba(34,197,94,0.14)";
      ctx.fillRect(x0, 0, Math.max(1, x1 - x0), cssH);
    }

    // Waveform.
    ctx.strokeStyle = "rgba(148,163,184,0.9)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    const step = cssW / waveform.length;
    for (let i = 0; i < waveform.length; i++) {
      const x = i * step;
      const y = mid - waveform[i] * mid * 0.95;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.stroke();

    ctx.textAlign = "center";
    ctx.font = "600 13px ui-sans-serif, system-ui, sans-serif";

    if (words?.length) {
      // Word labels + boundaries.
      for (const w of words) {
        if (w.start == null) continue;
        const x0 = xOf(w.start);
        const x1 = xOf(w.end);
        ctx.strokeStyle = "rgba(100,116,139,0.55)";
        ctx.beginPath();
        ctx.moveTo(x0, 0);
        ctx.lineTo(x0, cssH);
        ctx.stroke();
        if (w.index === selectedWord) {
          ctx.strokeStyle = "rgba(99,102,241,0.9)";
          ctx.lineWidth = 2;
          ctx.strokeRect(x0 + 1, 1, Math.max(2, x1 - x0 - 2), cssH - 2);
          ctx.lineWidth = 1;
        }
        ctx.fillStyle = w.correct === false ? "#fb7185" : "#4ade80";
        ctx.fillText(w.word, (x0 + x1) / 2, 16, Math.max(12, x1 - x0 - 2));
      }
      return;
    }

    // Phoneme labels + boundaries.
    for (const p of phonemes) {
      const x0 = xOf(p.start);
      const x1 = xOf(p.end);
      const cx = (x0 + x1) / 2;
      ctx.strokeStyle = "rgba(100,116,139,0.35)";
      ctx.beginPath();
      ctx.moveTo(x0, 0);
      ctx.lineTo(x0, cssH);
      ctx.stroke();
      ctx.fillStyle = p.verdict === "ERROR" ? "#fb7185" : "#4ade80";
      ctx.fillText(p.phoneme, cx, 16);
    }
  }, [waveform, rate, phonemes, duration, words, selectedWord]);

  return <canvas ref={canvasRef} className="waveform" aria-label="Waveform with phoneme spans" />;
}
