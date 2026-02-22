"""FastAPI dependency providers for auth, DB routing, and role enforcement."""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache

from fastapi import Depends, HTTPException, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.auth_engine import get_auth_db
from app.db.engine import get_db, tenant_pool
from app.services.auth import AuthContext, get_current_user, SESSION_COOKIE_NAME


@lru_cache
def get_settings_dep() -> Settings:
    return get_settings()


async def require_auth(
    request: Request,
    db: AsyncSession = Depends(get_auth_db),
) -> AuthContext:
    """Require a valid authenticated session. Returns AuthContext."""
    return await get_current_user(request, db)


def require_role(*allowed_roles: str):
    """Factory: returns a dependency that enforces role membership."""
    async def _check(auth: AuthContext = Depends(require_auth)) -> AuthContext:
        if auth.role not in allowed_roles:
            raise HTTPException(403, "Insufficient permissions")
        return auth
    return _check


async def get_company_db(
    auth: AuthContext = Depends(require_auth),
) -> AsyncSession:
    """Yield an async session for the authenticated user's tenant DB."""
    factory = tenant_pool.session_factory(auth.company_id)
    async with factory() as session:
        yield session


# ── Flexible auth: supports both session cookie AND tenant token ──

async def require_auth_or_tenant(
    request: Request,
    token: str = Query(default=""),
    auth_db: AsyncSession = Depends(get_auth_db),
) -> AuthContext:
    """Accept either a session cookie (owner/user) or a tenant link token.

    Tenant tokens provide a limited AuthContext with role='tenant'.
    """
    # Try session cookie first
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    if session_token:
        try:
            return await get_current_user(request, auth_db)
        except HTTPException:
            pass  # Fall through to try tenant token

    # Try tenant link token (from query param or form data)
    if not token:
        # Also check query string directly
        token = request.query_params.get("token", "")

    if token and ":" in token:
        company_id = token.split(":", 1)[0]
        factory = tenant_pool.session_factory(company_id)
        async with factory() as db:
            from app.db import crud
            link = await crud.get_tenant_link_by_token(db, token)
            if link and link.is_active:
                expires = link.expires_at.replace(tzinfo=timezone.utc) if link.expires_at.tzinfo is None else link.expires_at
                if expires > datetime.now(timezone.utc):
                    return AuthContext(
                        user_id="tenant",
                        company_id=company_id,
                        role="tenant",
                        email="",
                        display_name="Tenant",
                    )

    raise HTTPException(status_code=401, detail="Not authenticated")


async def get_company_db_flexible(
    auth: AuthContext = Depends(require_auth_or_tenant),
) -> AsyncSession:
    """Yield tenant DB session — works for both authenticated users and tenant token holders."""
    factory = tenant_pool.session_factory(auth.company_id)
    async with factory() as session:
        yield session
