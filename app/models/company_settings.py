"""Company settings — one row per tenant DB (no FK needed, it IS the company's DB)."""

from __future__ import annotations

from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, ULIDMixin
from app.models.encrypted_type import EncryptedString


class CompanySettings(Base, ULIDMixin):
    __tablename__ = "company_settings"

    llm_provider: Mapped[str] = mapped_column(String(30), default="openai")
    openai_api_key: Mapped[str] = mapped_column(EncryptedString(500), default="")
    anthropic_api_key: Mapped[str] = mapped_column(EncryptedString(500), default="")
    gemini_api_key: Mapped[str] = mapped_column(EncryptedString(500), default="")
    grok_api_key: Mapped[str] = mapped_column(EncryptedString(500), default="")
    default_link_days: Mapped[int] = mapped_column(Integer, default=7)
