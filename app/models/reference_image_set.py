from __future__ import annotations

from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ULIDMixin


class ReferenceImageSet(Base, ULIDMixin):
    __tablename__ = "reference_image_sets"

    room_template_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("room_templates.id", ondelete="CASCADE")
    )
    label: Mapped[str] = mapped_column(String(255), default="")
    capture_mode: Mapped[str] = mapped_column(String(20), default="traditional")
    image_count: Mapped[int] = mapped_column(Integer, default=0)

    room_template = relationship(
        "RoomTemplate", back_populates="reference_sets",
        foreign_keys=[room_template_id],
    )
    images = relationship(
        "ReferenceImage", back_populates="reference_set",
        lazy="selectin", cascade="all, delete-orphan",
    )
