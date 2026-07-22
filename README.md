---
title: Clario
emoji: 🗣️
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 8000
pinned: false
license: mit
short_description: AI phoneme error detection system
---

<!-- The YAML block above is Hugging Face Spaces metadata. On GitHub it renders
     as a small table; on HF it configures the Docker Space. See DEPLOY.md. -->

# 🗣️ Clario — Speech Clarity Coach

Clario turns the phoneme-error-detection model from
`notebooks/phoneme-error-detection.ipynb` into a full product: record (or
upload) yourself saying a word, and get **per-phoneme feedback** on which sounds
came out unclear — visualized on the waveform and scored 0–100%.

Built for speech-therapy practice and pronunciation training. Works on desktop
and mobile browsers (installable as a PWA).

```
┌───────────────┐   audio + word    ┌──────────────────────────────┐
│  React + Vite │ ────────────────► │  FastAPI backend             │
│  frontend     │                   │   espeak-ng → wav2vec2 align  │
│  (record/upload,                  │   → one 64×32 mel per phoneme │
│   waveform, score) ◄───────────── │   → CNN-BiLSTM classifier     │
└───────────────┘   phoneme verdicts└──────────────────────────────┘
```

## Repository layout

```
Clario/
├── models/
│   └── phoneme_error_model.keras     # trained CNN-BiLSTM (provided)
├── data/
│   └── phoneme_dataset.npz           # supplies training mel_mean/std (provided)
├── notebooks/                        # original Kaggle training/inference notebook
├── backend/                          # FastAPI inference service  (see backend/README.md)
└── frontend/                         # React + Vite web app       (see frontend/README.md)
```

## Quick start (Docker — recommended, zero local installs)

Everything (Python, Node, espeak-ng, TensorFlow, torch) is baked into the images.
You only need Docker (Rancher Desktop works).

```bash
# from the repo root
docker compose up --build
```

Then open **http://localhost:3000** (the API is on http://localhost:8010).

- Ports: the web app is on **3000** and the API on **8010** (8080/8000 are left
  free for other services). Change the host ports in `docker-compose.yml` if needed.
- The trained model (`./models`) and normalization stats (`./data`) are mounted
  automatically — no extra setup needed for training-exact scaling.
- First run downloads the ~1 GB wav2vec2 aligner (cached in a named volume, so
  later starts are fast). Watch readiness with `curl http://localhost:8010/api/health`.
- Mic recording needs `https` or `localhost` — `http://localhost:3000` qualifies.

---

## Quick start (local dev)

You need **two terminals** — one for the API, one for the web app.

### 1. Backend (Python 3.10/3.11 + espeak-ng)

```bash
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

> First launch installs `espeak-ng` (see backend/README.md) and downloads the
> ~1 GB wav2vec2 aligner once. For best accuracy, place `phoneme_dataset.npz`
> in `models/` so the API uses the training normalization stats.

### 2. Frontend (Node 18+)

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**. The dev server proxies `/api` to the backend,
so no extra config is needed. On your phone, open the same URL over your LAN
(e.g. `http://<your-ip>:5173`) — mic recording requires `https` or `localhost`,
so for phone testing use a tunnel (ngrok/Cloudflare) or run both over HTTPS.

## How a request flows

1. Browser records the mic (or takes an uploaded file), decodes it, resamples to
   **16 kHz mono**, and encodes a WAV — the exact format the pipeline expects.
2. `POST /api/analyze` with the WAV + target word.
3. Backend aligns the audio to the word's phonemes, scores each phoneme, and
   returns verdicts + a downsampled waveform.
4. UI paints the waveform with red (error) / green (clear) spans, a clarity ring,
   and a per-phoneme breakdown with error-probability meters.

## Notes & limitations

- The model was trained on **dysarthric vs. control** speech (UASpeech). It flags
  phonemes whose acoustics deviate from clear reference speech — a screening
  signal, not a clinical diagnosis.
- Accuracy depends on the normalization stats matching training — provide the
  `.npz` or the `mel_mean`/`mel_std` values (see backend/README.md).
- Tune sensitivity with `CLARIO_ERROR_THRESHOLD` (0.40 screening → 0.50 precise).

See **backend/README.md** and **frontend/README.md** for details.
