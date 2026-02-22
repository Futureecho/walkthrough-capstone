"""Auth DB models: Company, User, UserSession, PasswordReset, Invite.

These live in the central auth.db, separate from per-company tenant DBs.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from ulid import ULID


class AuthBase(DeclarativeBase):
    pass


class _AuthULIDMixin:
    id: Mapped[str] = mapped_column(
        String(26), primary_key=True, default=lambda: str(ULID())
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class Company(AuthBase, _AuthULIDMixin):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    users = relationship("User", back_populates="company", lazy="selectin")


class User(AuthBase, _AuthULIDMixin):
    __tablename__ = "users"

    company_id: Mapped[str] = mapped_column(String(26), ForeignKey("companies.id"))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="inspector")  # admin | inspector | viewer
    mfa_secret: Mapped[str] = mapped_column(String(500), default="")  # encrypted TOTP secret
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    company = relationship("Company", back_populates="users")


class UserSession(AuthBase, _AuthULIDMixin):
    __tablename__ = "user_sessions"

    user_id: Mapped[str] = mapped_column(String(26), ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ip_address: Mapped[str] = mapped_column(String(45), default="")


class PasswordReset(AuthBase, _AuthULIDMixin):
    __tablename__ = "password_resets"

    user_id: Mapped[str] = mapped_column(String(26), ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Invite(AuthBase, _AuthULIDMixin):
    __tablename__ = "invites"

    company_id: Mapped[str] = mapped_column(String(26), ForeignKey("companies.id"))
    email: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="inspector")
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    invited_by: Mapped[str] = mapped_column(String(26), ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
