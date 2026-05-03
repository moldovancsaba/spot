from __future__ import annotations

from fastapi import HTTPException, Request

from backend.services.auth_service import SESSION_COOKIE, auth_enabled, can, get_session


def session_payload(request: Request) -> dict | None:
    if not auth_enabled():
        return {
            "session_id": "local-auth-disabled",
            "role": "admin",
            "actor_name": "local-admin",
            "auth_enabled": False,
        }
    return get_session(request.cookies.get(SESSION_COOKIE))


def require_permission(request: Request, permission: str) -> dict:
    session = session_payload(request)
    if not session:
        raise HTTPException(status_code=401, detail="authentication required")
    if not can(str(session.get("role")), permission):
        raise HTTPException(status_code=403, detail=f"role '{session.get('role')}' is not allowed to perform '{permission}'")
    return session
