"""
Clario — Gradio entrypoint for Hugging Face Spaces (sdk: gradio).

Reuses the exact inference pipeline from `backend/app/` (espeak-ng -> wav2vec2
forced alignment -> one 64x32 mel per phoneme -> CNN-BiLSTM classifier) and
wraps it in a mobile-friendly Gradio UI: record or upload a word, get a
color-coded per-phoneme clarity breakdown, a waveform with error spans, and an
overall score.

This file is imported as module `app`; the reusable code is referenced as
`backend.app.*` (distinct fully-qualified name), so there is no clash.
"""
from __future__ import annotations

import logging
import os
import sys

import gradio as gr
import matplotlib

matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt
import numpy as np

# Ensure the repo root (this file's dir) is importable so `backend` resolves.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.app.audio import load_and_trim  # noqa: E402
from backend.app.config import get_settings  # noqa: E402
from backend.app.phonemes import espeak_available  # noqa: E402
from backend.app.pipeline import get_pipeline  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("clario.gradio")

S = get_settings()
PIPE = get_pipeline()

COLOR_MAP = {"error": "#f43f5e", "clear": "#22c55e"}
SUGGESTED = ["hello", "water", "yesterday", "computer", "beautiful", "seven", "purple", "animal"]


def _warmup() -> None:
    """Load models at startup so the first analysis isn't slow."""
    if os.environ.get("CLARIO_SKIP_WARMUP") == "1":
        log.info("CLARIO_SKIP_WARMUP=1 — skipping model warm-up.")
        return
    try:
        log.info("Warming up models…")
        PIPE.load()
        log.info("Models ready (device=%s, norm=%s).", PIPE.device, PIPE.normalization_desc)
    except Exception as exc:  # noqa: BLE001
        log.warning("Warm-up deferred to first request: %s", exc)


def _waveform_figure(wave: np.ndarray, results: list[dict], target_word: str):
    dur = len(wave) / S.sample_rate
    t = np.linspace(0, dur, len(wave))
    fig, ax = plt.subplots(figsize=(11, 3.2))
    ax.plot(t, wave, color="#94a3b8", linewidth=0.7)
    ymax = float(np.max(np.abs(wave))) or 1.0
    for r in results:
        is_err = r["verdict"] == "ERROR"
        ax.axvspan(r["start"], r["end"], color=("#f43f5e" if is_err else "#22c55e"), alpha=0.16)
        mid = (r["start"] + r["end"]) / 2
        ax.text(mid, ymax * 0.82, r["phoneme"], ha="center", fontsize=11,
                color=("#b91c1c" if is_err else "#15803d"), fontweight="bold")
    ax.set_title(f"“{target_word}” — red = predicted error, green = clear")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Amplitude")
    ax.set_xlim(0, dur)
    fig.tight_layout()
    return fig


def analyze(audio_path: str | None, target_word: str):
    """Gradio callback: -> (summary_md, highlighted_phonemes, waveform_fig, table_rows)."""
    target_word = (target_word or "").strip()
    empty = ("", [], None, [])

    if not target_word:
        return ("⚠️ **Enter a word to practise first.**", *empty[1:])
    if not audio_path:
        return ("⚠️ **Record or upload a recording first.**", *empty[1:])
    if not espeak_available():
        return ("❌ **espeak-ng is not installed on the server.**", *empty[1:])

    try:
        with open(audio_path, "rb") as f:
            data = f.read()
        wave = load_and_trim(data, S.sample_rate, S.trim_top_db)
    except Exception as exc:  # noqa: BLE001
        return (f"❌ **Could not read the audio:** {exc}", *empty[1:])

    try:
        results = PIPE.analyze(wave, target_word)
    except ValueError as exc:
        return (f"⚠️ {exc}", *empty[1:])
    except Exception as exc:  # noqa: BLE001
        log.exception("Analysis failed")
        return (f"❌ **Analysis failed:** {exc}", *empty[1:])

    if not results:
        return ("⚠️ **No phonemes could be aligned.** Check the word and recording.", *empty[1:])

    n_err = sum(1 for r in results if r["verdict"] == "ERROR")
    n = len(results)
    acc = round(100 * (1 - n_err / n))
    dur = round(len(wave) / S.sample_rate, 2)
    band = "🟢" if acc >= 85 else "🟠" if acc >= 60 else "🔴"

    summary = (
        f"### {band} Clarity: **{acc}%**  ·  {n - n_err}/{n} phonemes clear\n"
        f"Word “**{target_word}**” · {n_err} flagged · {dur}s · threshold {S.error_threshold}"
    )
    highlighted = [(f" {r['phoneme']} ", "error" if r["verdict"] == "ERROR" else "clear")
                   for r in results]
    fig = _waveform_figure(wave, results, target_word)
    table = [[r["phoneme"], f"{r['start']:.2f}–{r['end']:.2f}",
              f"{round(r['error_prob'] * 100)}%",
              "error" if r["verdict"] == "ERROR" else "clear"] for r in results]
    return summary, highlighted, fig, table


with gr.Blocks(title="Clario — Speech Clarity Coach", theme=gr.themes.Soft(
        primary_hue="indigo", secondary_hue="violet")) as demo:
    gr.Markdown(
        "# 🗣️ Clario — Speech Clarity Coach\n"
        "Record or upload yourself saying a word. Clario aligns your speech to the "
        "word's phonemes and highlights any sounds that came out unclear."
    )
    with gr.Row():
        with gr.Column(scale=1):
            word = gr.Textbox(label="Word to practise", value="hello", autofocus=True)
            gr.Examples(examples=[[w] for w in SUGGESTED], inputs=[word], label="Try a word")
            audio = gr.Audio(sources=["microphone", "upload"], type="filepath",
                             label="Record or upload the word")
            btn = gr.Button("Analyse", variant="primary")
        with gr.Column(scale=1):
            summary = gr.Markdown()
            phonemes = gr.HighlightedText(label="Per-phoneme verdict", color_map=COLOR_MAP,
                                          combine_adjacent=False, show_legend=True)
            wave_plot = gr.Plot(label="Waveform")
            table = gr.Dataframe(headers=["phoneme", "time (s)", "P(error)", "verdict"],
                                 label="Details", wrap=True)

    btn.click(analyze, inputs=[audio, word], outputs=[summary, phonemes, wave_plot, table])
    gr.Markdown(
        "<sub>CNN-BiLSTM phoneme-error model + wav2vec2 forced alignment · "
        "screening signal, not a clinical diagnosis.</sub>"
    )

if __name__ == "__main__":
    _warmup()
    demo.launch(server_name="0.0.0.0", server_port=int(os.environ.get("PORT", 7860)))
else:
    # HF imports this module (does not run __main__); warm up on import.
    _warmup()
