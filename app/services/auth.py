"""Authentication service: bcrypt password hashing + HTTP-only session cookies."""

from __future__ import annotations

import secrets
from fastapi import Request, HTTPException

import bcrypt


# In-memory session store {token: owner_id}
_owner_sessions: dict[str, str] = {}

SESSION_COOKIE_NAME = "owner_session"


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_session_token(owner_id: str) -> str:
    token = secrets.token_urlsafe(48)
    _owner_sessions[token] = owner_id
    return token


def remove_session_token(token: str) -> None:
    _owner_sessions.pop(token, None)


def get_owner_id_from_token(token: str) -> str | None:
    return _owner_sessions.get(token)


async def get_current_owner(request: Request) -> str:
    """FastAPI dependency: reads session cookie, returns owner_id or raises 401."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    owner_id = get_owner_id_from_token(token)
    if not owner_id:
        raise HTTPException(status_code=401, detail="Session expired")
    return owner_id
