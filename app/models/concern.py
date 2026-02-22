"""Concern model — tenant-flagged issues during inspection."""

from __future__ import annotations

from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ULIDMixin


class Concern(Base, ULIDMixin):
    __tablename__ = "concerns"

    session_id: Mapped[str] = mapped_column(String(26), ForeignKey("sessions.id"))
    room: Mapped[str] = mapped_column(String(200), default="")
    title: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(String(200), default="")
    file_path: Mapped[str] = mapped_column(String(500), default="")
    thumbnail_path: Mapped[str] = mapped_column(String(500), default="")

    session = relationship("Session", back_populates="concerns")
