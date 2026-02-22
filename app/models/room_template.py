from __future__ import annotations

from sqlalchemy import String, Integer, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ULIDMixin


class RoomTemplate(Base, ULIDMixin):
    __tablename__ = "room_templates"

    property_id: Mapped[str] = mapped_column(String(26), ForeignKey("properties.id"))
    name: Mapped[str] = mapped_column(String(255))
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    positions: Mapped[list] = mapped_column(JSON, default=list)
    capture_mode: Mapped[str] = mapped_column(String(20), default="traditional")

    property = relationship("Property", back_populates="room_templates")
    reference_images = relationship(
        "ReferenceImage", back_populates="room_template",
        lazy="selectin", cascade="all, delete-orphan",
    )
