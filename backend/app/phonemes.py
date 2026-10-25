"""
Grapheme -> IPA phoneme conversion via the espeak-ng CLI.

This mirrors the training/inference notebook exactly: it shells out to the
`espeak-ng` binary rather than using the `phonemizer` Python package, and strips
the same stress/length diacritics that are not part of the alignment model's
phone vocabulary.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from functools import lru_cache

# IPA diacritics produced by espeak that are NOT in the wav2vec2 phone vocab.
# (Primary stress U+02C8, secondary stress U+02CC, length mark U+02D0.)
_STRESS_MARKS = ("ˈ", "ˌ", "ː")


@lru_cache
def espeak_available() -> bool:
    return shutil.which("espeak-ng") is not None


def word_to_phonemes(word: str) -> list[str]:
    """IPA phonemes for a single word, as a list of individual symbols."""
    return list(_word_to_phonemes(word.strip()))


# Cached: a sentence would otherwise spawn one espeak process per word on
# every request, and practice words/sentences repeat a lot.
@lru_cache(maxsize=4096)
def _word_to_phonemes(word: str) -> tuple[str, ...]:
    if not word:
        return ()
    try:
        out = subprocess.run(
            ["espeak-ng", "-q", "--ipa", "-v", "en-us", word],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
        ).stdout.strip()
    except FileNotFoundError as exc:  # espeak-ng not on PATH
        raise RuntimeError(
            "espeak-ng is not installed or not on PATH. Install it and retry "
            "(Windows: install espeak-ng and add it to PATH; "
            "Linux: apt-get install espeak-ng; macOS: brew install espeak-ng)."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("espeak-ng timed out.") from exc

    for m in _STRESS_MARKS:
        out = out.replace(m, "")
    return tuple(ch for ch in out if ch.strip())


# A word = letters/digits, optionally joined by apostrophes ("don't", "it’s").
# Punctuation is dropped so "Hello, world!" -> ["Hello", "world"].
_WORD_RE = re.compile(r"[^\W_]+(?:['’][^\W_]+)*")


def tokenize_sentence(text: str) -> list[str]:
    """Split a sentence into the words that get scored individually."""
    return _WORD_RE.findall(text)


def transcript_to_phonemes(transcript: str) -> list[str]:
    """IPA phonemes for a whole transcript (space-separated words)."""
    phones: list[str] = []
    for w in transcript.strip().split():
        phones.extend(word_to_phonemes(w))
    return phones
