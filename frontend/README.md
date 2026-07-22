# Clario — Frontend (React + Vite)

Responsive, mobile-first web app (installable PWA) for the Clario speech-clarity
API.

## Features

- 🎙 In-browser mic recording → decoded, resampled to 16 kHz mono, WAV-encoded
  client-side (no ffmpeg needed on the server).
- ⤴ Upload an existing audio file instead of recording.
- Suggested practice words + free-text input.
- Waveform painted with per-phoneme red/green spans and IPA labels.
- Clarity score ring + per-phoneme error-probability meters.
- Live backend health indicator.

## Setup

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

`npm run dev` proxies `/api` → `http://localhost:8000` (configurable via
`VITE_API_TARGET`). Make sure the backend is running.

## Build

```bash
npm run build      # outputs to dist/
npm run preview    # serve the production build locally
```

For production set `VITE_API_BASE` to your API origin (see `.env.example`). You
can also serve `dist/` behind the same origin as the API to avoid CORS entirely.

## Microphone & HTTPS

Browsers only allow `getUserMedia` on `https://` or `localhost`. To test on a
phone, use `localhost` via a tunnel (ngrok / Cloudflare Tunnel) or serve over
HTTPS.

## Structure

```
src/
├── App.jsx                 # main screen + state
├── lib/
│   ├── api.js              # fetch wrappers (/api/health, /api/analyze)
│   └── audio.js            # Recorder + 16 kHz mono WAV encoding
└── components/
    ├── WaveformChart.jsx   # canvas waveform + phoneme spans
    ├── PhonemeList.jsx     # per-phoneme breakdown
    └── ScoreRing.jsx       # clarity gauge
```
