# =============================================================================
# Clario — single-image deployment (Hugging Face Spaces / any Docker host)
# Builds the React frontend, then runs FastAPI which serves BOTH the API and
# the built web UI on one port. One HTTPS origin, no CORS.
# =============================================================================

# ---- Stage 1: build the React frontend -------------------------------------
FROM node:20-alpine AS frontend
WORKDIR /fe
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build          # -> /fe/dist

# ---- Stage 2: Python backend + static UI -----------------------------------
FROM python:3.11-slim

# System deps: espeak-ng (phonemizer CLI), ffmpeg (audio fallback), libsndfile.
RUN apt-get update && apt-get install -y --no-install-recommends \
        espeak-ng ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# HF Spaces runs the container as a non-root user (uid 1000). Create it and use
# its home for caches so the aligner download at runtime has a writable dir.
RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    HF_HOME=/home/user/.cache/huggingface \
    PYTHONUNBUFFERED=1 \
    TF_CPP_MIN_LOG_LEVEL=3 \
    PIP_DEFAULT_TIMEOUT=600 \
    PIP_RETRIES=10

# CPU-only torch first (the default wheel bundles ~2 GB of CUDA libs).
RUN pip install --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cpu \
        torch==2.2.2 torchaudio==2.2.2
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# App code, model, and the built UI (owned by the runtime user).
COPY --chown=user backend/app /srv/backend/app
COPY --chown=user models /srv/models
COPY --from=frontend --chown=user /fe/dist /srv/static

ENV CLARIO_MODEL_PATH=/srv/models/phoneme_error_model.keras \
    CLARIO_STATIC_DIR=/srv/static \
    CLARIO_DEVICE=cpu \
    CLARIO_CORS_ORIGINS=*

USER user
WORKDIR /srv/backend

# Optionally bake the wav2vec2 aligner + Whisper ASR (target-word verification)
# into the image so cold starts are fast and don't re-download them at runtime.
# Set to 0 for a quicker/lighter build.
ARG PREFETCH_ALIGNER=1
RUN if [ "$PREFETCH_ALIGNER" = "1" ]; then \
      python -c "from transformers import Wav2Vec2ForCTC, Wav2Vec2CTCTokenizer; \
m='facebook/wav2vec2-lv-60-espeak-cv-ft'; \
Wav2Vec2CTCTokenizer.from_pretrained(m); Wav2Vec2ForCTC.from_pretrained(m)" && \
      python -c "from transformers import WhisperForConditionalGeneration, WhisperProcessor; \
m='openai/whisper-tiny.en'; \
WhisperProcessor.from_pretrained(m); WhisperForConditionalGeneration.from_pretrained(m)"; \
    fi

# HF Spaces routes external HTTPS to this port (see app_port in README).
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
