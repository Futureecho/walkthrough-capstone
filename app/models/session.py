from __future__ import annotations

from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ULIDMixin


class Session(Base, ULIDMixin):
    __tablename__ = "sessions"

    property_id: Mapped[str] = mapped_column(String(26), ForeignKey("properties.id"))
    type: Mapped[str] = mapped_column(String(20))  # move_in | move_out
    tenant_name: Mapped[str] = mapped_column(String(255), default="")

    property = relationship("Property", back_populates="sessions")
    captures = relationship("Capture", back_populates="session", lazy="selectin")
