"""
Per-user practice history.

  GET    /api/history              paginated attempt summaries (newest first)
  GET    /api/history/{id}         full result of one attempt (same shape as /analyze)
  GET    /api/history/{id}/audio   the recording, if it was stored
  DELETE /api/history/{id}         remove an attempt and its recording
"""
from __future__ import annotations

import base64
import logging
import uuid

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, Response

from . import db
from .auth import current_user
from .config import get_settings
from .schemas import AnalyzeResponse, AttemptDetail, AttemptSummary, HistoryPage

log = logging.getLogger("clario.history")

router = APIRouter(prefix="/api/history", tags=["history"])

_SUMMARY_FIELDS = (
    "id,created_at,mode,target_word,accuracy,n_phonemes,n_errors,"
    "n_words,n_words_correct,word_accuracy,audio_path"
)


# The plot waveform (up to 2000 floats in -1..1) is stored as base64 int8:
# ~2.7 KB instead of ~20 KB of JSON numbers, and plenty precise for drawing.
def _pack_waveform(wave: list[float]) -> str:
    q = (np.clip(np.asarray(wave, dtype=np.float32), -1, 1) * 127).astype(np.int8)
    return base64.b64encode(q.tobytes()).decode("ascii")


def _unpack_waveform(data: str | None) -> list[float]:
    if not data:
        return []
    q = np.frombuffer(base64.b64decode(data), dtype=np.int8)
    return [round(float(v), 3) for v in q / 127.0]


def save_attempt(user: dict, result: AnalyzeResponse, audio: bytes, content_type: str) -> str:
    """Persist one analysis for `user`; returns the new attempt id."""
    row = result.model_dump(mode="json", exclude={"waveform", "attempt_id"})
    row.update(user_id=user["id"], waveform_q=_pack_waveform(result.waveform), audio_path=None)

    if get_settings().store_audio and audio:
        row["audio_path"] = f"{user['id']}/{uuid.uuid4()}.wav"
        # Generic uploads arrive as application/octet-stream; the browser
        # client always sends 16 kHz WAV.
        db.upload(row["audio_path"], audio,
                  content_type if content_type.startswith("audio/") else "audio/wav")
    try:
        return db.insert("attempts", row)["id"]
    except Exception:
        if row["audio_path"]:          # don't leave an orphaned recording behind
            try:
                db.remove(row["audio_path"])
            except Exception:  # noqa: BLE001
                pass
        raise


def _own_attempt(user: dict, attempt_id: str, fields: str = "*") -> dict:
    try:
        attempt_id = str(uuid.UUID(attempt_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Attempt not found.") from exc
    rows, _ = db.select("attempts", {
        "select": fields, "id": f"eq.{attempt_id}", "user_id": f"eq.{user['id']}",
    })
    if not rows:
        raise HTTPException(status_code=404, detail="Attempt not found.")
    return rows[0]


@router.get("", response_model=HistoryPage)
def list_attempts(
    user: dict = Depends(current_user),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    mode: str | None = Query(None, pattern="^(word|sentence)$"),
) -> HistoryPage:
    params = {
        "select": _SUMMARY_FIELDS,
        "user_id": f"eq.{user['id']}",
        "order": "created_at.desc",
        "limit": limit,
        "offset": offset,
    }
    if mode:
        params["mode"] = f"eq.{mode}"
    rows, total = db.select("attempts", params, count=True)
    return HistoryPage(
        items=[AttemptSummary(**r, has_audio=r["audio_path"] is not None) for r in rows],
        total=total or 0,
    )


@router.get("/{attempt_id}", response_model=AttemptDetail)
def get_attempt(attempt_id: str, user: dict = Depends(current_user)) -> AttemptDetail:
    row = _own_attempt(user, attempt_id)
    return AttemptDetail(
        **{k: v for k, v in row.items() if k not in ("user_id", "waveform_q", "audio_path")},
        attempt_id=row["id"],
        waveform=_unpack_waveform(row.get("waveform_q")),
        has_audio=row["audio_path"] is not None,
    )


@router.get("/{attempt_id}/audio")
def get_attempt_audio(attempt_id: str, user: dict = Depends(current_user)) -> Response:
    row = _own_attempt(user, attempt_id, "audio_path")
    if row["audio_path"] is None:
        raise HTTPException(status_code=404, detail="No recording stored for this attempt.")
    try:
        data, content_type = db.download(row["audio_path"])
    except db.DBError as exc:
        raise HTTPException(status_code=404, detail="Recording is missing.") from exc
    return Response(content=data, media_type=content_type)


@router.delete("/{attempt_id}", status_code=204)
def delete_attempt(attempt_id: str, user: dict = Depends(current_user)) -> Response:
    row = _own_attempt(user, attempt_id, "id,audio_path")
    db.delete("attempts", {"id": f"eq.{row['id']}", "user_id": f"eq.{user['id']}"})
    if row["audio_path"]:
        try:
            db.remove(row["audio_path"])
        except db.DBError as exc:
            log.warning("Could not delete recording %s: %s", row["audio_path"], exc)
    return Response(status_code=204)
