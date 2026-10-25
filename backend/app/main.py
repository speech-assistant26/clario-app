"""
Clario API — FastAPI service wrapping the phoneme-error-detection pipeline.

Endpoints:
  GET  /api/health          liveness + model/espeak/db status
  POST /api/analyze         audio file + target word/sentence -> per-phoneme (+ per-word) verdicts
  /api/auth/*               accounts           (see auth.py, needs Supabase)
  /api/history/*            practice history   (see history.py, needs Supabase)
"""
from __future__ import annotations

import logging
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import __version__
from . import auth, db, history
from .audio import assess_quality, downsample_for_plot, load_and_trim
from .config import get_settings
from .phonemes import espeak_available, tokenize_sentence
from .pipeline import get_pipeline, summarize_words
from .schemas import AnalyzeResponse, HealthResponse, Mode, PhonemeResult, WordResult

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("clario")
# httpx logs every Supabase request at INFO; keep only its warnings.
logging.getLogger("httpx").setLevel(logging.WARNING)

settings = get_settings()

# Inference runs in a worker thread (so the event loop stays responsive), but
# one analysis at a time: TF/torch already use every core, and Keras predict
# isn't guaranteed thread-safe.
_inference_lock = threading.Lock()


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

    if db.history_enabled():
        try:
            db.ensure_setup()
            log.info("History enabled (Supabase connected).")
        except Exception as exc:  # noqa: BLE001
            log.warning("Supabase not ready — history will fail until it is: %s", exc)
    else:
        log.info("History disabled (CLARIO_SUPABASE_URL / CLARIO_SUPABASE_SERVICE_KEY not set).")
    yield


app = FastAPI(title="Clario API", version=__version__, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(history.router)


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
        history_enabled=db.history_enabled(),
        db_connected=db.ping(),
    )


def _verify(pipeline, wave, target: str, words: list[str], mode: Mode) -> tuple[str | None, list]:
    """Whisper sanity check -> (warning or None, per-word heard flags)."""
    try:
        if mode == "sentence":
            v = pipeline.verify_sentence(wave, words)
            missing = [w for w, h in zip(words, v["heard"]) if h is False]
            if v["checked"] and len(missing) > len(words) / 2:
                return (
                    "Most of this sentence wasn't recognised. The breakdown below still "
                    "assumes the target text — try again if you said something else.",
                    v["heard"],
                )
            return None, v["heard"]

        v = pipeline.verify_word(wave, target)
        if v["checked"] and not v["matched"]:
            return (
                f"This doesn't sound like “{target}”. "
                "The breakdown below still assumes the target word — try again if that's not right.",
                [None],
            )
    except Exception as exc:  # noqa: BLE001
        log.warning("Word verification failed, continuing without it: %s", exc)
    return None, [None] * len(words)


def _run_analysis(
    data: bytes, target: str, words: list[str], mode: Mode, error_threshold: float | None
) -> AnalyzeResponse:
    """Blocking part of /analyze (decode -> quality gate -> verify -> classify)."""
    try:
        wave = load_and_trim(data, settings.sample_rate, settings.trim_top_db)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Could not decode audio: {exc}") from exc

    if settings.enable_quality_gate:
        reason = assess_quality(wave, settings.min_rms_dbfs, settings.max_noise_flatness)
        if reason:
            raise HTTPException(status_code=422, detail=reason)

    pipeline = get_pipeline()
    with _inference_lock:
        word_warning, heard = _verify(pipeline, wave, target, words, mode)
        try:
            results = pipeline.analyze(
                wave, target, error_threshold=error_threshold,
                words=words if mode == "sentence" else None,
            )
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
            detail="No phonemes could be aligned. Check the target text and recording.",
        )

    word_rows = summarize_words(words, results, settings.word_pass_accuracy, heard)
    scored = [w for w in word_rows if w["correct"] is not None]
    n_words_correct = sum(1 for w in scored if w["correct"])
    n_errors = sum(1 for r in results if r["verdict"] == "ERROR")
    n_phonemes = len(results)

    return AnalyzeResponse(
        mode=mode,
        target_word=target,
        phonemes=[PhonemeResult(**r) for r in results],
        n_errors=n_errors,
        n_phonemes=n_phonemes,
        accuracy=round(1 - n_errors / n_phonemes, 4) if n_phonemes else 0.0,
        words=[WordResult(**w) for w in word_rows],
        n_words=len(scored),
        n_words_correct=n_words_correct,
        word_accuracy=round(n_words_correct / len(scored), 4) if scored else None,
        duration_sec=round(len(wave) / settings.sample_rate, 3),
        error_threshold=error_threshold if error_threshold is not None else settings.error_threshold,
        word_warning=word_warning,
        waveform=downsample_for_plot(wave),
        waveform_rate=settings.sample_rate,
    )


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(
    audio: UploadFile = File(..., description="Recording of the spoken word/sentence (WAV preferred)"),
    target_word: str = Form(..., description="The word (or sentence) the speaker was asked to say"),
    mode: Mode = Form("word", description='"word" (default) or "sentence" (adds per-word scoring)'),
    error_threshold: float | None = Form(
        None, description="Optional per-request override of the error-probability cutoff"
    ),
    user: dict | None = Depends(auth.optional_user),
) -> AnalyzeResponse:
    target_word = " ".join(target_word.split())
    if not target_word:
        raise HTTPException(status_code=422, detail="target_word must not be empty.")
    if not espeak_available():
        raise HTTPException(
            status_code=503,
            detail="espeak-ng is not installed on the server; cannot derive phonemes.",
        )

    if mode == "sentence":
        words = tokenize_sentence(target_word)
        if not words:
            raise HTTPException(status_code=422, detail="The sentence has no words to score.")
        if len(words) > settings.max_sentence_words:
            raise HTTPException(
                status_code=422,
                detail=f"Sentences are limited to {settings.max_sentence_words} words.",
            )
    else:
        words = [target_word]

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

    result = await run_in_threadpool(_run_analysis, data, target_word, words, mode, error_threshold)

    if user is not None:
        # Saving is best-effort: a DB hiccup shouldn't throw away the result.
        try:
            result.attempt_id = await run_in_threadpool(
                history.save_attempt, user, result, data, audio.content_type or "audio/wav"
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not save attempt to history: %s", exc)
    return result


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
