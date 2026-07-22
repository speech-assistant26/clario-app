"""Audio loading + trimming, decoupled from the model pipeline."""
from __future__ import annotations

import io
import tempfile
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf


def load_and_trim(data: bytes, sample_rate: int, trim_top_db: float) -> np.ndarray:
    """
    Decode arbitrary audio bytes to a mono float32 waveform at `sample_rate`,
    then trim leading/trailing silence — exactly the training preprocessing.

    Tries libsndfile (soundfile) first for WAV/FLAC/OGG; falls back to librosa's
    audioread path (needs ffmpeg) for compressed formats like webm/mp3.
    """
    y = _decode(data, sample_rate)
    y, _ = librosa.effects.trim(y, top_db=trim_top_db)
    return y.astype(np.float32)


def _decode(data: bytes, sample_rate: int) -> np.ndarray:
    # Fast path: libsndfile can read WAV/FLAC/OGG straight from memory.
    try:
        y, sr = sf.read(io.BytesIO(data), dtype="float32", always_2d=False)
        if y.ndim > 1:               # stereo -> mono
            y = y.mean(axis=1)
        if sr != sample_rate:
            y = librosa.resample(y, orig_sr=sr, target_sr=sample_rate)
        return y.astype(np.float32)
    except Exception:
        pass

    # Fallback: write to a temp file and let librosa/audioread handle it.
    suffix = ""
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    try:
        y, _ = librosa.load(tmp_path, sr=sample_rate, mono=True)
        return y.astype(np.float32)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def assess_quality(
    wave: np.ndarray, min_rms_dbfs: float, max_flatness: float
) -> str | None:
    """
    Reject audio before it reaches the (expensive) alignment/classification
    models. Returns a human-readable rejection reason, or None if the audio
    looks like usable speech.
    """
    if len(wave) == 0:
        return "No audio detected. Please record again and make sure your microphone is working."

    rms = float(np.sqrt(np.mean(np.square(wave)) + 1e-12))
    dbfs = 20 * np.log10(rms + 1e-12)
    if dbfs < min_rms_dbfs:
        return "Recording is too quiet. Please speak louder or move closer to the microphone."

    flatness = float(np.mean(librosa.feature.spectral_flatness(y=wave)))
    if flatness > max_flatness:
        return "This sounds like background noise rather than speech. Please try recording again in a quieter space."

    return None


def downsample_for_plot(wave: np.ndarray, max_points: int = 2000) -> list[float]:
    """Reduce the waveform to at most `max_points` samples for client drawing."""
    n = len(wave)
    if n == 0:
        return []
    if n <= max_points:
        return [round(float(v), 4) for v in wave]
    # Peak-preserving decimation: keep max abs value within each bucket.
    idx = np.linspace(0, n, max_points + 1).astype(int)
    out = []
    for a, b in zip(idx[:-1], idx[1:]):
        seg = wave[a:b] if b > a else wave[a:a + 1]
        j = int(np.argmax(np.abs(seg)))
        out.append(round(float(seg[j]), 4))
    return out
