"""
Clario API — FastAPI service wrapping the phoneme-error-detection pipeline.

Endpoints:
  GET  /api/health          liveness + model/espeak status
  POST /api/analyze         audio file + target word -> per-phoneme verdicts
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import __version__
from .audio import assess_quality, downsample_for_plot, load_and_trim
from .config import get_settings
from .phonemes import espeak_available
from .pipeline import get_pipeline
from .schemas import AnalyzeResponse, HealthResponse, PhonemeResult, WordCheck

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("clario")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm up the models at startup so the first request isn't slow. If loading
    # fails (e.g. no network to fetch the aligner) we log and continue — /health
    # will report the degraded state and /analyze will surface the real error.
    try:
        log.info("Warming up models…")
        get_pipeline().load()
        log.info("Models ready.")
    except Exception as exc:  # noqa: BLE001
        log.warning("Model warm-up failed (will retry on first request): %s", exc)
    yield


app = FastAPI(title="Clario API", version=__version__, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    pipe = get_pipeline()
    return HealthResponse(
        status="ok",
        model_loaded=pipe.is_loaded and pipe._clf is not None,
        align_model_loaded=pipe.is_loaded and pipe._align_model is not None,
        whisper_loaded=pipe.whisper_loaded,
        espeak_available=espeak_available(),
        device=pipe.device,
        normalization=pipe.normalization_desc,
    )


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(
    audio: UploadFile = File(..., description="Recording of the spoken word (WAV preferred)"),
    target_word: str = Form(..., description="The word/phrase the speaker was asked to say"),
    error_threshold: float | None = Form(
        None, description="Optional per-request override of the error-probability cutoff"
    ),
) -> AnalyzeResponse:
    target_word = target_word.strip()
    if not target_word:
        raise HTTPException(status_code=422, detail="target_word must not be empty.")
    if not espeak_available():
        raise HTTPException(
            status_code=503,
            detail="espeak-ng is not installed on the server; cannot derive phonemes.",
        )

    if error_threshold is not None:
        error_threshold = max(
            settings.min_error_threshold, min(settings.max_error_threshold, error_threshold)
        )

    data = await audio.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(data) == 0:
        raise HTTPException(status_code=422, detail="Empty audio upload.")
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail=f"Audio exceeds {settings.max_upload_mb} MB.")

    try:
        wave = load_and_trim(data, settings.sample_rate, settings.trim_top_db)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Could not decode audio: {exc}") from exc

    if settings.enable_quality_gate:
        reason = assess_quality(wave, settings.min_rms_dbfs, settings.max_noise_flatness)
        if reason:
            raise HTTPException(status_code=422, detail=reason)

    pipeline = get_pipeline()

    try:
        verification = pipeline.verify_word(wave, target_word)
    except Exception as exc:  # noqa: BLE001
        log.warning("Word verification failed, continuing without it: %s", exc)
        verification = {"checked": False, "matched": True, "heard": None, "similarity": None}

    # A word mismatch is ADVISORY, not fatal. Blocking the analysis here was the
    # wrong call for the target population: severely dysarthric speech is exactly
    # what a small ASR model mis-transcribes, so a hard 422 withheld feedback from
    # the users who need it most. We now warn and analyse anyway — the phoneme
    # verdicts stand on their own, and the user decides what to make of them.
    warning: str | None = None
    if verification["checked"] and not verification["matched"]:
        heard = verification.get("heard")
        warning = (
            f"This doesn’t sound like “{target_word}”"
            + (f" — it sounded more like “{heard}”." if heard else ".")
            + " The results below may be less reliable; re-record if you meant to"
            " say a different word."
        )
        log.info("Word mismatch (advisory): target=%r heard=%r similarity=%s",
                 target_word, heard, verification.get("similarity"))

    try:
        results = pipeline.analyze(wave, target_word, error_threshold=error_threshold)
    except ValueError as exc:                 # bad input (too short / no phonemes)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:                # environment problem (espeak/model)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:                   # noqa: BLE001
        log.exception("Analysis failed")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc

    if not results:
        raise HTTPException(
            status_code=422,
            detail="No phonemes could be aligned. Check the target word and recording.",
        )

    n_errors = sum(1 for r in results if r["verdict"] == "ERROR")
    n_phonemes = len(results)
    duration = round(len(wave) / settings.sample_rate, 3)

    return AnalyzeResponse(
        target_word=target_word,
        phonemes=[PhonemeResult(**r) for r in results],
        n_errors=n_errors,
        n_phonemes=n_phonemes,
        accuracy=round(1 - n_errors / n_phonemes, 4) if n_phonemes else 0.0,
        duration_sec=duration,
        error_threshold=error_threshold if error_threshold is not None else settings.error_threshold,
        waveform=downsample_for_plot(wave),
        waveform_rate=settings.sample_rate,
        warning=warning,
        word_check=WordCheck(**verification),
    )


# --- Single-deployment mode -------------------------------------------------
# When CLARIO_STATIC_DIR points at a built frontend (e.g. on Hugging Face
# Spaces, where FastAPI serves both the API and the web UI), mount it at "/".
# This is added AFTER all /api routes and /docs, so they still match first.
# Locally (docker-compose, no such env var) we keep a plain JSON root instead.
_static_dir = os.environ.get("CLARIO_STATIC_DIR")
if _static_dir and Path(_static_dir).is_dir():
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="ui")
    log.info("Serving frontend from %s", _static_dir)
else:
    @app.get("/")
    def root() -> dict:
        return {"name": "Clario API", "version": __version__, "docs": "/docs"}
