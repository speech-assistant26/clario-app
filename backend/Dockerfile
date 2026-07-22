# Clario backend — FastAPI + TensorFlow + torch + espeak-ng
FROM python:3.11-slim

# System deps: espeak-ng (phonemizer CLI), ffmpeg (audio fallback), libsndfile (soundfile)
RUN apt-get update && apt-get install -y --no-install-recommends \
        espeak-ng \
        ffmpeg \
        libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    TF_CPP_MIN_LOG_LEVEL=3 \
    HF_HOME=/root/.cache/huggingface \
    PIP_DEFAULT_TIMEOUT=600 \
    PIP_RETRIES=10

WORKDIR /app

# 1) Install CPU-only torch/torchaudio FIRST from the PyTorch CPU index. The
#    default PyPI wheel bundles ~2 GB of CUDA libraries, which is what timed out.
#    The +cpu build satisfies the `torch==2.2.2` pin in requirements.txt, so the
#    next step won't re-download it.
RUN pip install --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cpu \
        torch==2.2.2 torchaudio==2.2.2

# 2) Install the rest (torch already satisfied).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Model + norm stats are mounted at runtime (see docker-compose).
ENV CLARIO_MODEL_PATH=/models/phoneme_error_model.keras \
    CLARIO_DATASET_NPZ_PATH=/data/phoneme_dataset.npz

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
