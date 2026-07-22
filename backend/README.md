# Clario — Backend (FastAPI)

Serves the phoneme-level speech-error-detection pipeline as a REST API.

## Pipeline (mirrors the training notebook exactly)

1. **Load + trim** the uploaded audio to 16 kHz mono (`librosa`).
2. **Grapheme → IPA** for the target word via the `espeak-ng` CLI.
3. **Forced alignment** with `facebook/wav2vec2-lv-60-espeak-cv-ft` + `torchaudio.functional.forced_align` → phoneme time spans.
4. **Mel crop**: one mel per phoneme (64 × 32), truncated/zero-padded to 32 frames.
5. **Classification**: the CNN-BiLSTM (`models/phoneme_error_model.keras`) scores each phoneme; ≥ threshold (0.50) → flagged as an error.

> **Model version:** v02 / v8 "control-baseline" — control speech anchors the
> "correct" class, so healthy recordings come back mostly OK. (v01 used sliding
> 64×16 sub-windows with mean aggregation; v02 uses one 64×32 mel per phoneme.)

## Prerequisites

- **Python 3.10 or 3.11** (TensorFlow 2.16 does not support 3.12+ on all platforms).
- **espeak-ng** binary on `PATH`:
  - Windows: install [espeak-ng releases](https://github.com/espeak-ng/espeak-ng/releases), then add its folder to `PATH`. Verify with `espeak-ng --version`.
  - macOS: `brew install espeak-ng`
  - Linux: `sudo apt-get install espeak-ng`
- First run downloads the ~1 GB wav2vec2 aligner from Hugging Face (cached afterwards).

## Setup

```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

# CPU-only torch (small download; avoids the ~2 GB CUDA wheel):
pip install torch==2.2.2 torchaudio==2.2.2 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

> If pip times out on the big wheels (slow connection), rerun with a longer
> timeout: `pip install --timeout 600 --retries 10 -r requirements.txt`.

### Normalization stats (important for accuracy)

The model was trained on **globally z-scored** mel windows. Stats are resolved in this order:

1. `CLARIO_MEL_MEAN` / `CLARIO_MEL_STD` env overrides (if set).
2. `mel_mean`/`mel_std` read from `../data/phoneme_dataset.npz` (shipped with the repo).
3. Baked-in constants in `config.py` (`-2.4128` / `10.2228`, decoded from that same npz).

All three give training-exact scaling. `/api/health` shows the active mode
(`global-zscore` vs `per-clip-zscore`).

## Run

```bash
uvicorn app.main:app --reload --port 8000
```

- Swagger UI: http://localhost:8000/docs
- Health: http://localhost:8000/api/health

## API

### `POST /api/analyze`
`multipart/form-data`:
- `audio` — WAV file (16 kHz mono preferred; the frontend sends exactly this).
- `target_word` — the word the speaker was asked to say.
- `error_threshold` — optional per-request override of the P(error) cutoff, clamped to
  `[CLARIO_MIN_ERROR_THRESHOLD, CLARIO_MAX_ERROR_THRESHOLD]` (0.30–0.70 by default).

Before scoring, the request is rejected with `422` if:
- the audio is too quiet or looks like background noise rather than speech (the
  quality gate — see `CLARIO_MIN_RMS_DBFS` / `CLARIO_MAX_NOISE_FLATNESS`), or
- a Whisper ASR pass thinks a completely different word was spoken (not a
  pronunciation judge — just a sanity check that the right word was attempted).

Otherwise returns per-phoneme verdicts, an overall clarity score, and a downsampled waveform for plotting.

### `GET /api/health`
Liveness + model/espeak/device/normalization status.

## Configuration

All settings use the `CLARIO_` env prefix (see `.env.example`). Key ones:

| Var | Default | Meaning |
|-----|---------|---------|
| `CLARIO_ERROR_THRESHOLD` | `0.50` | P(error) cutoff (0.40 screening · 0.45 balanced) |
| `CLARIO_MIN_ERROR_THRESHOLD` / `_MAX_ERROR_THRESHOLD` | `0.30` / `0.70` | clamp range for the per-request threshold override |
| `CLARIO_ENABLE_QUALITY_GATE` | `true` | reject too-quiet/noise-only recordings before analysis |
| `CLARIO_MIN_RMS_DBFS` | `-40.0` | quieter than this (dBFS) -> "too quiet" |
| `CLARIO_MAX_NOISE_FLATNESS` | `0.6` | spectral flatness above this -> "just noise" |
| `CLARIO_ENABLE_WORD_VERIFICATION` | `true` | Whisper sanity check that the target word was attempted |
| `CLARIO_WHISPER_MODEL_NAME` | `openai/whisper-tiny.en` | ASR model used for that check |
| `CLARIO_WORD_MATCH_THRESHOLD` | `0.45` | similarity below which the word is considered "different" |
| `CLARIO_DEVICE` | `auto` | `cpu` / `cuda` / `auto` |
| `CLARIO_CORS_ORIGINS` | `*` | comma-separated allowed origins |
| `CLARIO_MEL_MEAN`/`_STD` | — | normalization override |
