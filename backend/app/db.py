"""
Supabase access (users, attempt history, recordings) over its HTTPS REST APIs.

Plain HTTPS on port 443 on purpose: it works from hosts that block database
ports (e.g. Hugging Face Spaces allow only 80/443/8080 outbound), and it avoids
the heavy supabase-py dependency tree.

Optional: with no CLARIO_SUPABASE_URL / CLARIO_SUPABASE_SERVICE_KEY the app
runs exactly as before, just without accounts/history.

  Tables (backend/supabase/schema.sql):  users, attempts
  Storage bucket (created on startup):   recordings  (private)
"""
from __future__ import annotations

import logging
import threading

import httpx

from .config import get_settings

log = logging.getLogger("clario.db")

BUCKET = "recordings"

_client: httpx.Client | None = None
_lock = threading.Lock()


class DBError(RuntimeError):
    """A failed Supabase call. `code` is the Postgres/PostgREST error code if any."""

    def __init__(self, status: int, message: str, code: str | None = None) -> None:
        super().__init__(f"Supabase error {status}: {message}")
        self.status = status
        self.code = code


def history_enabled() -> bool:
    s = get_settings()
    return bool(s.supabase_url and s.supabase_service_key)


def _http() -> httpx.Client:
    global _client
    s = get_settings()
    if not history_enabled():
        raise RuntimeError("History is disabled (CLARIO_SUPABASE_URL / _SERVICE_KEY not set).")
    if _client is None:
        with _lock:
            if _client is None:
                key = s.supabase_service_key
                headers = {"apikey": key}
                # Legacy service_role keys are JWTs and go in Authorization too;
                # new-style sb_secret_ keys must only be sent as `apikey`.
                if key.startswith("eyJ"):
                    headers["Authorization"] = f"Bearer {key}"
                # Accept the "Data API" URL from the dashboard too (…/rest/v1/).
                base = s.supabase_url.strip().rstrip("/").removesuffix("/rest/v1")
                _client = httpx.Client(base_url=base, headers=headers, timeout=20.0)
    return _client


def _check(res: httpx.Response) -> httpx.Response:
    if res.is_success:
        return res
    try:
        body = res.json()
        message = body.get("message") or body.get("error") or res.text
        code = body.get("code") or body.get("statusCode")
    except ValueError:
        message, code = res.text, None
    raise DBError(res.status_code, str(message)[:300], str(code) if code else None)


# --- tables (PostgREST) --------------------------------------------------------
def select(table: str, params: dict, count: bool = False) -> tuple[list[dict], int | None]:
    """GET rows. With count=True also returns the total matching rows."""
    headers = {"Prefer": "count=exact"} if count else {}
    res = _check(_http().get(f"/rest/v1/{table}", params=params, headers=headers))
    total = None
    if count:
        # Content-Range: "0-19/42"  (or "*/0" when empty)
        total = int(res.headers.get("content-range", "*/0").rsplit("/", 1)[-1])
    return res.json(), total


def insert(table: str, row: dict) -> dict:
    res = _check(_http().post(
        f"/rest/v1/{table}", json=row, headers={"Prefer": "return=representation"}
    ))
    return res.json()[0]


def delete(table: str, params: dict) -> None:
    _check(_http().delete(f"/rest/v1/{table}", params=params))


# --- storage -------------------------------------------------------------------
def upload(path: str, data: bytes, content_type: str) -> None:
    _check(_http().post(
        f"/storage/v1/object/{BUCKET}/{path}", content=data,
        headers={"Content-Type": content_type, "x-upsert": "false"},
    ))


def download(path: str) -> tuple[bytes, str]:
    res = _check(_http().get(f"/storage/v1/object/{BUCKET}/{path}"))
    return res.content, res.headers.get("content-type", "audio/wav")


def remove(path: str) -> None:
    _check(_http().request(
        "DELETE", f"/storage/v1/object/{BUCKET}", json={"prefixes": [path]}
    ))


# --- lifecycle -----------------------------------------------------------------
def ping() -> bool:
    if not history_enabled():
        return False
    try:
        select("users", {"select": "id", "limit": 1})
        return True
    except Exception:  # noqa: BLE001
        return False


def ensure_setup() -> None:
    """Create the private recordings bucket if needed and check the schema exists."""
    res = _http().post(
        "/storage/v1/bucket", json={"id": BUCKET, "name": BUCKET, "public": False}
    )
    if not res.is_success and "already exists" not in res.text.lower():
        _check(res)
    try:
        select("attempts", {"select": "id", "limit": 1})
    except DBError as exc:
        if exc.status == 404 or exc.code in ("PGRST205", "42P01"):
            raise RuntimeError(
                "Supabase tables are missing - run backend/supabase/schema.sql in the "
                "Supabase SQL Editor."
            ) from exc
        raise
    log.info("Supabase ready (bucket %r, tables present).", BUCKET)
