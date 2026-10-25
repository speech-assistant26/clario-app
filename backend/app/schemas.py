"""Pydantic response/request models for the Clario API."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Mode = Literal["word", "sentence"]


class PhonemeResult(BaseModel):
    phoneme: str = Field(..., description="IPA symbol for this aligned phoneme")
    start: float = Field(..., description="Start time in seconds (trimmed timebase)")
    end: float = Field(..., description="End time in seconds (trimmed timebase)")
    verdict: str = Field(..., description='"ERROR" or "ok"')
    error_prob: float = Field(..., description="P(error) for this phoneme, 0..1")
    align_score: float = Field(..., description="Forced-alignment confidence, 0..1")
    word_index: int = Field(0, description="Index into `words` (always 0 in word mode)")


class WordResult(BaseModel):
    word: str
    index: int
    start: float | None = None
    end: float | None = None
    n_phonemes: int
    n_errors: int
    accuracy: float | None = Field(None, description="Phoneme clarity within this word, 0..1")
    correct: bool | None = Field(None, description="None when the word couldn't be scored")
    # Whisper's opinion on whether the word was said at all (None = not checked).
    heard: bool | None = None


class AnalyzeResponse(BaseModel):
    mode: Mode = "word"
    target_word: str
    phonemes: list[PhonemeResult]
    n_errors: int
    n_phonemes: int
    accuracy: float = Field(..., description="Fraction of phonemes produced correctly, 0..1")
    # Sentence mode: per-word roll-up (word mode: a single entry).
    words: list[WordResult] = []
    n_words: int = Field(0, description="Words that could be scored")
    n_words_correct: int = 0
    word_accuracy: float | None = Field(None, description="n_words_correct / n_words")
    duration_sec: float
    error_threshold: float
    # Set when Whisper thinks a different word was spoken. Non-blocking - the
    # phoneme results below are still returned; this is just a heads-up.
    word_warning: str | None = None
    # Downsampled mono waveform (-1..1) for drawing on the client, plus its rate.
    waveform: list[float]
    waveform_rate: int
    # Set when the attempt was saved to the signed-in user's history.
    attempt_id: str | None = None


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    align_model_loaded: bool
    whisper_loaded: bool
    espeak_available: bool
    device: str
    normalization: str
    history_enabled: bool = False
    db_connected: bool = False


# --- accounts ----------------------------------------------------------------
class Credentials(BaseModel):
    username: str = Field(..., min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(..., min_length=8, max_length=72)


class UserOut(BaseModel):
    id: str
    username: str
    created_at: datetime


class AuthResponse(BaseModel):
    token: str
    user: UserOut


# --- history -----------------------------------------------------------------
class AttemptSummary(BaseModel):
    id: str
    created_at: datetime
    mode: Mode
    target_word: str
    accuracy: float
    n_phonemes: int
    n_errors: int
    n_words: int
    n_words_correct: int
    word_accuracy: float | None = None
    has_audio: bool


class HistoryPage(BaseModel):
    items: list[AttemptSummary]
    total: int


class AttemptDetail(AnalyzeResponse):
    id: str
    created_at: datetime
    has_audio: bool
