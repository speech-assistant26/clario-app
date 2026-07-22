"""Pydantic response/request models for the Clario API."""
from __future__ import annotations

from pydantic import BaseModel, Field


class PhonemeResult(BaseModel):
    phoneme: str = Field(..., description="IPA symbol for this aligned phoneme")
    start: float = Field(..., description="Start time in seconds (trimmed timebase)")
    end: float = Field(..., description="End time in seconds (trimmed timebase)")
    verdict: str = Field(..., description='"ERROR" or "ok"')
    error_prob: float = Field(..., description="P(error) for this phoneme, 0..1")
    align_score: float = Field(..., description="Forced-alignment confidence, 0..1")


class AnalyzeResponse(BaseModel):
    target_word: str
    phonemes: list[PhonemeResult]
    n_errors: int
    n_phonemes: int
    accuracy: float = Field(..., description="Fraction of phonemes produced correctly, 0..1")
    duration_sec: float
    error_threshold: float
    # Downsampled mono waveform (-1..1) for drawing on the client, plus its rate.
    waveform: list[float]
    waveform_rate: int


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    align_model_loaded: bool
    whisper_loaded: bool
    espeak_available: bool
    device: str
    normalization: str
