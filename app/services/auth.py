"""Authentication service: DB-backed sessions, bcrypt passwords, TOTP MFA."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

import bcrypt
import pyotp
from fastapi import Request, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth_models import User, UserSession

SESSION_COOKIE_NAME = "session_token"
SESSION_MAX_AGE_DAYS = 7


@dataclass
class AuthContext:
    user_id: str
    company_id: str
    role: str  # 'admin' | 'inspector' | 'viewer'
    email: str
    display_name: str


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def _hash_token(token: str) -> str:
    """SHA-256 hash of a session/reset token for DB storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def create_session(user: User, db: AsyncSession, ip_address: str = "") -> str:
    """Create a DB-backed session. Returns the raw token (not the hash)."""
    token = secrets.token_urlsafe(48)
    token_hash = _hash_token(token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=SESSION_MAX_AGE_DAYS)

    session = UserSession(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
        ip_address=ip_address,
    )
    db.add(session)
    await db.commit()
    return token


async def validate_session(token: str, db: AsyncSession) -> User | None:
    """Look up session by token hash, return User if valid."""
    token_hash = _hash_token(token)
    result = await db.execute(
        select(UserSession).where(
            UserSession.token_hash == token_hash,
            UserSession.expires_at > datetime.now(timezone.utc),
        )
    )
    session = result.scalars().first()
    if not session:
        return None

    user = await db.get(User, session.user_id)
    if not user or not user.is_active:
        return None
    return user


async def remove_session(token: str, db: AsyncSession) -> None:
    """Delete a session by token."""
    token_hash = _hash_token(token)
    result = await db.execute(
        select(UserSession).where(UserSession.token_hash == token_hash)
    )
    session = result.scalars().first()
    if session:
        await db.delete(session)
        await db.commit()


async def remove_all_user_sessions(user_id: str, db: AsyncSession) -> None:
    """Invalidate all sessions for a user (e.g. after password change)."""
    result = await db.execute(
        select(UserSession).where(UserSession.user_id == user_id)
    )
    sessions = result.scalars().all()
    for s in sessions:
        await db.delete(s)
    await db.commit()


async def get_current_user(request: Request, db: AsyncSession) -> AuthContext:
    """Read session cookie, validate, return AuthContext or raise 401."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = await validate_session(token, db)
    if not user:
        raise HTTPException(status_code=401, detail="Session expired")

    return AuthContext(
        user_id=user.id,
        company_id=user.company_id,
        role=user.role,
        email=user.email,
        display_name=user.display_name,
    )


# ── MFA helpers ───────────────────────────────────────────

def generate_mfa_secret() -> str:
    """Generate a new TOTP secret (base32)."""
    return pyotp.random_base32()


def get_mfa_provisioning_uri(secret: str, email: str, issuer: str = "Walkthru-X") -> str:
    """Get the otpauth:// URI for QR code generation."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=issuer)


def verify_mfa_code(secret: str, code: str) -> bool:
    """Verify a TOTP code against a secret (with 1-step window for clock drift)."""
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)
