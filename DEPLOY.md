# Deploying Clario for free on Hugging Face Spaces

Clario runs as a **single Docker image**: the React UI is built and served by
FastAPI alongside the API, on one HTTPS origin. HF Spaces' free CPU tier
(16 GB RAM, 2 vCPU) comfortably fits the TensorFlow + PyTorch + wav2vec2 stack.

## What gets deployed

- The root [`Dockerfile`](Dockerfile) builds the frontend, installs the backend,
  bakes in the wav2vec2 aligner, and serves everything on port **8000**.
- Only the **5 MB** `models/phoneme_error_model.keras` ships as an artifact — the
  normalization stats are baked into `config.py`, so the 54 MB `.npz` is **not
  needed**.
- HF metadata lives in the YAML header at the top of [`README.md`](README.md)
  (`sdk: docker`, `app_port: 8000`).

## One-time setup

1. Create a free account at https://huggingface.co.
2. Create a **New Space** → https://huggingface.co/new-space
   - **Owner**: you · **Space name**: `clario`
   - **SDK**: **Docker** → **Blank**
   - **Hardware**: CPU basic (free) · **Visibility**: Public (or Private)
3. Create an access token (write): https://huggingface.co/settings/tokens

## Push the code

From the project root

```bash
git init
git add .
git commit -m "Clario — HF Space (single image)"

# Replace <username> with your HF username:
git remote add space https://huggingface.co/spaces/<username>/clario
git branch -M main
git push space main
```

When prompted for a password, paste your **HF access token** (not your account
password). Alternatively use the CLI:

```bash
pip install -U huggingface_hub
huggingface-cli login          # paste the write token
```

> The `.gitignore` already excludes `node_modules/`, `.venv/`, `data/` (the big
> npz) and build output, so the push is small. The 5 MB `.keras` model commits
> fine without git-LFS.

## First build & run

- HF builds the Docker image (a few minutes — it compiles the frontend and bakes
  in the aligner). Watch the **Logs** tab.
- When it says the app is running, open the Space URL:
  `https://<username>-clario.hf.space`
- The page is served over HTTPS, so **microphone recording works**.

## Notes & tuning

- **Cold start**: after the Space sleeps (free tier idles out), the next visit
  triggers a wake — the first analysis takes ~10–30 s while models load; then
  it's a few seconds per request.
- **Health check**: `https://<username>-clario.hf.space/api/health` should report
  `model_loaded`, `align_model_loaded`, `whisper_loaded`, `espeak_available`, and
  `normalization: global-zscore`.
- **Change the threshold** without a rebuild: Space → **Settings** →
  **Variables and secrets** → add `CLARIO_ERROR_THRESHOLD = 0.45` (or 0.40). Users
  can also override it per-request from the UI's sensitivity slider (clamped by
  `CLARIO_MIN_ERROR_THRESHOLD` / `CLARIO_MAX_ERROR_THRESHOLD`).
- **Tune the quality gate / word check**: `CLARIO_MIN_RMS_DBFS`,
  `CLARIO_MAX_NOISE_FLATNESS`, `CLARIO_ENABLE_WORD_VERIFICATION`,
  `CLARIO_WORD_MATCH_THRESHOLD` — see backend/README.md.
- **Faster/lighter build**: set a build arg `PREFETCH_ALIGNER=0` (Space →
  Settings → Variables) to skip baking the aligner and Whisper — smaller image,
  but they download on first boot instead (~1.2 GB aligner + ~150 MB Whisper).
- **Updating**: commit and `git push space main` again; HF rebuilds automatically.

## Alternative: split hosting

If you'd rather serve the UI from a static CDN (Cloudflare Pages / Vercel /
Netlify — all free) and keep only the API on the Space:

1. Deploy the backend to the Space as above (it still serves the UI too; just
   ignore that).
2. Build the frontend with `VITE_API_BASE=https://<username>-clario.hf.space`
   and deploy `frontend/dist` to your static host.
3. Set `CLARIO_CORS_ORIGINS` on the Space to your Pages/Vercel origin.
