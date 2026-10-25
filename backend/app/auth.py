"""
Username/password accounts: bcrypt-hashed passwords, stateless JWT bearer tokens.

  POST /api/auth/register   {username, password} -> {token, user}
  POST /api/auth/login      {username, password} -> {token, user}
  GET  /api/auth/me         -> user   (requires Authorization: Bearer <token>)
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import uuid

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import db
from .config import get_settings
from .db import history_enabled
from .schemas import AuthResponse, Credentials, UserOut

log = logging.getLogger("clario.auth")

router = APIRouter(prefix="/api/auth", tags=["auth"])
_bearer = HTTPBearer(auto_error=False)
_ALGORITHM = "HS256"


@lru_cache
def _secret() -> str:
    s = get_settings().jwt_secret
    if s:
        return s
    log.warning(
        "CLARIO_JWT_SECRET is not set - using a random per-process secret. "
        "Everyone will be logged out whenever the server restarts."
    )
    return secrets.token_urlsafe(48)


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def _check_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("ascii"))
    except ValueError:
        return False


def _make_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": user_id, "iat": now, "exp": now + timedelta(days=get_settings().jwt_expire_days)}
    return jwt.encode(payload, _secret(), algorithm=_ALGORITHM)


_PUBLIC_FIELDS = "id,username,created_at"


def _user_out(row: dict) -> UserOut:
    return UserOut(id=row["id"], username=row["username"], created_at=row["created_at"])


def _require_history() -> None:
    if not history_enabled():
        raise HTTPException(status_code=503, detail="Accounts are not enabled on this server.")


def _load_user(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, _secret(), algorithms=[_ALGORITHM])
        user_id = str(uuid.UUID(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        return None
    rows, _ = db.select("users", {"select": _PUBLIC_FIELDS, "id": f"eq.{user_id}"})
    return rows[0] if rows else None


async def optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict | None:
    """The signed-in user, or None (anonymous use is always allowed)."""
    if creds is None or not history_enabled():
        return None
    return await run_in_threadpool(_load_user, creds.credentials)


async def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    _require_history()
    user = await run_in_threadpool(_load_user, creds.credentials) if creds else None
    if user is None:
        raise HTTPException(status_code=401, detail="Please sign in again.")
    return user


def _password_ok_length(password: str) -> None:
    # bcrypt only looks at the first 72 bytes; reject rather than truncate.
    if len(password.encode("utf-8")) > 72:
        raise HTTPException(status_code=422, detail="Password is too long (max 72 bytes).")


@router.post("/register", response_model=AuthResponse)
def register(body: Credentials) -> AuthResponse:
    _require_history()
    _password_ok_length(body.password)
    try:
        row = db.insert("users", {
            "username": body.username.lower(),
            "password_hash": _hash_password(body.password),
        })
    except db.DBError as exc:
        if exc.code == "23505":                       # unique_violation
            raise HTTPException(status_code=409, detail="That username is taken.") from exc
        raise
    return AuthResponse(token=_make_token(row["id"]), user=_user_out(row))


@router.post("/login", response_model=AuthResponse)
def login(body: Credentials) -> AuthResponse:
    _require_history()
    _password_ok_length(body.password)
    rows, _ = db.select("users", {"select": "*", "username": f"eq.{body.username.lower()}"})
    if not rows or not _check_password(body.password, rows[0]["password_hash"]):
        raise HTTPException(status_code=401, detail="Wrong username or password.")
    return AuthResponse(token=_make_token(rows[0]["id"]), user=_user_out(rows[0]))


@router.get("/me", response_model=UserOut)
def me(user: dict = Depends(current_user)) -> UserOut:
    return _user_out(user)
