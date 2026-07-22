"""
Phoneme-level error-detection pipeline (faithful port of notebook cell 8).

Flow for one recording + target word:
  1. load + trim audio  (single timebase for everything downstream)
  2. forced-align the waveform to the word's IPA phonemes (wav2vec2 + torchaudio)
  3. slice each phoneme into sliding sub-windows (n_mels x subwin_frames)
  4. mel-spectrogram each window, normalize, classify with the CNN-BiLSTM
  5. aggregate window P(error) -> one verdict per phoneme

Heavy models (wav2vec2 aligner, Keras classifier) load lazily and once.
"""
from __future__ import annotations

import difflib
import logging
import threading

import librosa
import numpy as np

from .config import Settings, get_settings
from .phonemes import transcript_to_phonemes

log = logging.getLogger("clario.pipeline")


class PhonemeErrorPipeline:
    def __init__(self, settings: Settings | None = None) -> None:
        self.s = settings or get_settings()
        self.device = self.s.resolved_device()
        self._lock = threading.Lock()

        # Lazily initialised heavy objects.
        self._clf = None                # Keras classifier
        self._align_model = None        # wav2vec2 CTC
        self._tokenizer = None
        self._vocab: dict[str, int] = {}
        self._blank_id: int = 0
        self._mel_mean: float | None = None
        self._mel_std: float | None = None
        self._whisper_processor = None
        self._whisper_model = None
        self._loaded = False

    # ---- lifecycle ---------------------------------------------------------
    def load(self) -> None:
        """Load all models + normalization stats. Safe to call repeatedly."""
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            self._load_classifier()
            self._load_aligner()
            if self.s.enable_word_verification:
                self._load_whisper()
            self._mel_mean, self._mel_std = self.s.load_norm_stats()
            if self._mel_mean is None:
                log.warning(
                    "No mel_mean/mel_std found (phoneme_dataset.npz missing and "
                    "no env override). Falling back to per-clip normalization."
                )
            else:
                log.info("mel_mean=%.3f mel_std=%.3f", self._mel_mean, self._mel_std)
            self._loaded = True

    def _load_classifier(self) -> None:
        import os
        os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
        from tensorflow.keras.models import load_model  # noqa: E402
        if not self.s.model_path.exists():
            raise FileNotFoundError(f"Model not found: {self.s.model_path}")
        log.info("Loading classifier: %s", self.s.model_path)
        self._clf = load_model(self.s.model_path)

    def _load_aligner(self) -> None:
        import torch
        from transformers import Wav2Vec2CTCTokenizer, Wav2Vec2ForCTC
        log.info("Loading alignment model: %s (device=%s)", self.s.align_model_name, self.device)
        self._tokenizer = Wav2Vec2CTCTokenizer.from_pretrained(self.s.align_model_name)
        self._align_model = Wav2Vec2ForCTC.from_pretrained(self.s.align_model_name).to(self.device)
        self._align_model.eval()
        self._blank_id = self._tokenizer.pad_token_id
        self._vocab = self._tokenizer.get_vocab()
        self._torch = torch

    def _load_whisper(self) -> None:
        from transformers import WhisperForConditionalGeneration, WhisperProcessor
        log.info("Loading Whisper ASR: %s (device=%s)", self.s.whisper_model_name, self.device)
        self._whisper_processor = WhisperProcessor.from_pretrained(self.s.whisper_model_name)
        self._whisper_model = WhisperForConditionalGeneration.from_pretrained(
            self.s.whisper_model_name
        ).to(self.device)
        self._whisper_model.eval()

    @property
    def normalization_desc(self) -> str:
        if not self._loaded:
            return "not loaded"
        return "global-zscore" if self._mel_mean is not None else "per-clip-zscore"

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def whisper_loaded(self) -> bool:
        return self._whisper_model is not None

    # ---- alignment ---------------------------------------------------------
    def _emission(self, waveform_t):
        torch = self._torch
        with torch.inference_mode():
            logits = self._align_model(waveform_t.to(self.device)).logits
            return torch.log_softmax(logits, dim=-1)

    def align(self, wave: np.ndarray, transcript: str) -> list[tuple[str, float, float, float]]:
        """Return [(phoneme, start_sec, end_sec, score), ...] for the waveform."""
        import torchaudio
        torch = self._torch
        if len(wave) < self.s.sample_rate * 0.05:
            raise ValueError("Audio too short after trimming (<50ms). Record a bit longer.")

        phonemes = transcript_to_phonemes(transcript)
        tokens, kept = [], []
        for p in phonemes:
            if p in self._vocab:
                tokens.append(self._vocab[p])
                kept.append(p)
        if not tokens:
            raise ValueError(f"No valid phonemes for '{transcript}'.")

        waveform_t = torch.tensor(wave).unsqueeze(0)
        emission = self._emission(waveform_t)
        targets = torch.tensor([tokens], dtype=torch.int32, device=self.device)
        aligned, scores = torchaudio.functional.forced_align(
            emission, targets, blank=self._blank_id
        )
        aligned, scores = aligned[0], scores[0].exp()
        spans = torchaudio.functional.merge_tokens(aligned, scores)

        num_frames = emission.size(1)
        ratio = len(wave) / num_frames / self.s.sample_rate
        return [
            (p, float(sp.start * ratio), float(sp.end * ratio), float(sp.score))
            for sp, p in zip(spans, kept[: len(spans)])
        ]

    # ---- feature extraction ------------------------------------------------
    def crop_mel(self, wave: np.ndarray, start_sec: float, end_sec: float) -> np.ndarray:
        """One mel per phoneme -> (n_mels, fixed_frames), truncated/zero-padded."""
        s = max(0.0, start_sec - self.s.context_pad_sec)
        e = end_sec + self.s.context_pad_sec
        sr = self.s.sample_rate
        clip = wave[int(s * sr): min(int(e * sr), len(wave))]
        if len(clip) == 0:
            clip = np.zeros(int(0.05 * sr), dtype=np.float32)

        mel = librosa.power_to_db(
            librosa.feature.melspectrogram(y=clip, sr=sr, n_mels=self.s.n_mels)
        )
        frames = self.s.fixed_frames
        if mel.shape[1] < frames:
            mel = np.pad(mel, ((0, 0), (0, frames - mel.shape[1])), mode="constant")
        else:
            mel = mel[:, :frames]
        return mel

    def _normalize(self, mels: np.ndarray) -> np.ndarray:
        if self._mel_mean is not None and self._mel_std is not None:
            return (mels - self._mel_mean) / self._mel_std
        # Fallback: per-clip z-score (used only when training stats are absent).
        mean = float(mels.mean())
        std = float(mels.std() + 1e-8)
        return (mels - mean) / std

    # ---- target-word verification (Whisper) --------------------------------
    def transcribe(self, wave: np.ndarray) -> str:
        torch = self._torch
        inputs = self._whisper_processor(wave, sampling_rate=self.s.sample_rate, return_tensors="pt")
        input_features = inputs.input_features.to(self.device)
        with torch.inference_mode():
            ids = self._whisper_model.generate(input_features, max_new_tokens=30)
        return self._whisper_processor.batch_decode(ids, skip_special_tokens=True)[0].strip()

    def _normalize_for_match(self, text: str) -> str:
        # Whisper's own normalizer (spelled-out numbers <-> digits, punctuation,
        # casing, common contractions) so "seven" and a transcribed "7" line up.
        try:
            return self._whisper_processor.tokenizer.normalize(text)
        except Exception:
            return text.lower().strip(" .,!?\"'")

    def verify_word(self, wave: np.ndarray, target_word: str) -> dict:
        """
        Rough check that the recording contains the target word at all. This
        is NOT a pronunciation judge (the phoneme classifier handles that) -
        it only catches a completely different word being spoken.
        """
        if not self.s.enable_word_verification or not self.whisper_loaded:
            return {"checked": False, "matched": True, "heard": None, "similarity": None}

        heard_raw = self.transcribe(wave)
        heard = self._normalize_for_match(heard_raw)
        target = self._normalize_for_match(target_word)

        words_heard = heard.split() or [""]
        similarity = max(difflib.SequenceMatcher(None, target, w).ratio() for w in words_heard)
        matched = similarity >= self.s.word_match_threshold or target in heard or (heard and heard in target)
        return {"checked": True, "matched": matched, "heard": heard_raw, "similarity": round(similarity, 3)}

    # ---- top-level ---------------------------------------------------------
    def analyze(
        self, wave: np.ndarray, target_word: str, error_threshold: float | None = None
    ) -> list[dict]:
        """Per-phoneme results for a pre-trimmed waveform + its target word."""
        self.load()
        segments = self.align(wave, target_word)
        if not segments:
            return []

        threshold = error_threshold if error_threshold is not None else self.s.error_threshold

        # v8: one mel per phoneme, classified in a single batched predict.
        mels = np.stack([self.crop_mel(wave, s, e) for _, s, e, _ in segments])
        mels = mels[..., np.newaxis]                    # (n_phon, n_mels, frames, 1)
        mels = self._normalize(mels)
        probs = self._clf.predict(mels, verbose=0)[:, 1]  # P(error) per phoneme

        results: list[dict] = []
        for (phon, s, e, align_sc), p in zip(segments, probs):
            p = float(p)
            verdict = "ERROR" if p >= threshold else "ok"
            results.append({
                "phoneme": phon,
                "start": round(s, 4),
                "end": round(e, 4),
                "verdict": verdict,
                "error_prob": round(p, 4),
                "align_score": round(align_sc, 4),
            })
        return results


# Process-wide singleton.
_pipeline: PhonemeErrorPipeline | None = None
_singleton_lock = threading.Lock()


def get_pipeline() -> PhonemeErrorPipeline:
    global _pipeline
    if _pipeline is None:
        with _singleton_lock:
            if _pipeline is None:
                _pipeline = PhonemeErrorPipeline()
    return _pipeline
