from __future__ import annotations

from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ULIDMixin


class OwnerSettings(Base, ULIDMixin):
    __tablename__ = "owner_settings"

    owner_id: Mapped[str] = mapped_column(String(26), ForeignKey("owners.id"))
    llm_provider: Mapped[str] = mapped_column(String(30), default="openai")
    openai_api_key: Mapped[str] = mapped_column(String(500), default="")
    anthropic_api_key: Mapped[str] = mapped_column(String(500), default="")
    gemini_api_key: Mapped[str] = mapped_column(String(500), default="")
    grok_api_key: Mapped[str] = mapped_column(String(500), default="")
    default_link_days: Mapped[int] = mapped_column(Integer, default=7)

    owner = relationship("Owner", back_populates="settings")
