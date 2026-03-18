from __future__ import annotations

import os
import secrets
import time


SESSION_COOKIE = "spot_session"
SESSION_TTL_SECONDS = 12 * 60 * 60
ALLOWED_ROLES = {"operator", "reviewer", "acceptance_lead", "admin"}
ROLE_PERMISSIONS = {
    "operator": {"view", "upload", "start_run", "manage_run", "download_artifact"},
    "reviewer": {"view", "review"},
    "acceptance_lead": {"view", "download_artifact", "signoff"},
    "admin": {"view", "upload", "start_run", "manage_run", "download_artifact", "review", "signoff"},
}

_SESSIONS: dict[str, dict] = {}


def auth_enabled() -> bool:
    return os.getenv("SPOT_AUTH_ENABLED", "1") != "0"


def local_access_code() -> str:
    return os.getenv("SPOT_LOCAL_ACCESS_CODE", "spot-local")


def create_session(*, role: str, actor_name: str) -> dict:
    session_id = secrets.token_urlsafe(24)
    payload = {
        "session_id": session_id,
        "role": role,
        "actor_name": actor_name,
        "created_at": int(time.time()),
        "expires_at": int(time.time()) + SESSION_TTL_SECONDS,
    }
    _SESSIONS[session_id] = payload
    return payload


def get_session(session_id: str | None) -> dict | None:
    if not session_id:
        return None
    payload = _SESSIONS.get(session_id)
    if not payload:
        return None
    if int(payload.get("expires_at", 0)) < int(time.time()):
        _SESSIONS.pop(session_id, None)
        return None
    return payload


def delete_session(session_id: str | None) -> None:
    if session_id:
        _SESSIONS.pop(session_id, None)


def can(role: str, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())
