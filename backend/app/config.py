"""
Central configuration for Clario's inference service.

Every constant that affects the model's output MUST match the values used during
training (notebook `phoneme-error-detection-v01.ipynb`). Changing any of these
silently degrades accuracy, so they live in one place and are documented.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import numpy as np
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project layout:  <root>/backend/app/config.py  ->  <root>
ROOT_DIR = Path(__file__).resolve().parents[2]

# Global mel normalization stats decoded from the shipped phoneme_dataset.npz
# (v02 / v8 control-baseline model). Used as a baked-in fallback so scaling
# stays training-exact even if the .npz is moved/removed. Env vars or the .npz
# still take precedence if present.
_KNOWN_MEL_MEAN = -2.41279196739197
_KNOWN_MEL_STD = 10.222767829895


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CLARIO_", env_file=".env", extra="ignore")

    # --- Artifacts -----------------------------------------------------------
    # The trained CNN-BiLSTM classifier (Keras 3 .keras format).
    model_path: Path = ROOT_DIR / "models" / "phoneme_error_model.keras"
    # Dataset archive holding the global mel normalization stats (mel_mean/std).
    # Only the two scalar members are read (np.load is lazy per-key), so the
    # 130 MB feature array inside is never loaded into memory.
    dataset_npz_path: Path = ROOT_DIR / "data" / "phoneme_dataset.npz"

    # --- Alignment model (HuggingFace) ---------------------------------------
    align_model_name: str = "facebook/wav2vec2-lv-60-espeak-cv-ft"
    # Torch device: "cpu", "cuda", or "auto".
    device: str = "auto"

    # --- Audio / feature params (MUST match training) ------------------------
    # v02 / v8: ONE mel per phoneme, 64 mel-bins x FIXED_FRAMES, truncated or
    # zero-padded to exactly FIXED_FRAMES frames (no sliding sub-windows).
    sample_rate: int = 16000
    n_mels: int = 64
    fixed_frames: int = 32    # model input width (was sub-windowed in v01)
    context_pad_sec: float = 0.02
    trim_top_db: float = 20.0

    # --- Decision --------------------------------------------------------------
    # Per-phoneme P(error) >= threshold  ->  flagged as ERROR.
    # 0.40 screening (catch more) · 0.45 balanced · 0.50 precise (v8 default).
    error_threshold: float = 0.50
    # Clients may override the threshold per-request (UI sensitivity slider),
    # clamped to this range so it can't be pushed into a useless extreme.
    min_error_threshold: float = 0.30
    max_error_threshold: float = 0.70

    # --- Audio quality gate (reject before spending compute on it) -----------
    # Recordings quieter than this (dBFS, RMS-based) are rejected as "too quiet".
    min_rms_dbfs: float = -40.0
    # Spectral flatness above this (0..1, 1 = pure noise) is rejected as "just noise".
    max_noise_flatness: float = 0.6
    enable_quality_gate: bool = True

    # --- Target-word verification (Whisper ASR) ------------------------------
    # Catches a completely different word being spoken (not a pronunciation
    # judge - that's the phoneme classifier's job - just a sanity check).
    enable_word_verification: bool = True
    whisper_model_name: str = "openai/whisper-tiny.en"
    # Similarity ratio (0..1) below which the heard word is considered a
    # different word rather than a mispronunciation of the target.
    word_match_threshold: float = 0.45

    # --- Normalization fallback ----------------------------------------------
    # Used ONLY when the .npz is absent. If both are None we fall back to
    # per-clip z-scoring at inference time (functional, slightly less accurate).
    mel_mean: float | None = None
    mel_std: float | None = None

    # --- Server --------------------------------------------------------------
    cors_origins: str = "*"          # comma-separated list, or "*"
    max_upload_mb: int = 25

    def resolved_device(self) -> str:
        if self.device != "auto":
            return self.device
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"

    def load_norm_stats(self) -> tuple[float | None, float | None]:
        """Resolve (mel_mean, mel_std) with this precedence:
        1. explicit env overrides (CLARIO_MEL_MEAN / CLARIO_MEL_STD)
        2. values stored inside phoneme_dataset.npz
        3. baked-in constants decoded from the shipped .npz (still training-exact)
        """
        if self.mel_mean is not None and self.mel_std is not None:
            return self.mel_mean, self.mel_std
        if self.dataset_npz_path.exists():
            try:
                d = np.load(self.dataset_npz_path, allow_pickle=True)
                mean = float(d["mel_mean"]) if "mel_mean" in d else None
                std = float(d["mel_std"]) if "mel_std" in d else None
                if mean is not None and std is not None:
                    return mean, std
            except Exception:
                pass
        return _KNOWN_MEL_MEAN, _KNOWN_MEL_STD

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
