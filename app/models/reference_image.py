from __future__ import annotations

from typing import Optional

from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ULIDMixin


class ReferenceImage(Base, ULIDMixin):
    __tablename__ = "reference_images"

    room_template_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("room_templates.id", ondelete="CASCADE")
    )
    set_id: Mapped[Optional[str]] = mapped_column(
        String(26), ForeignKey("reference_image_sets.id", ondelete="CASCADE"),
        nullable=True,
    )
    position_hint: Mapped[str] = mapped_column(String(100))
    seq: Mapped[int] = mapped_column(Integer, default=1)
    file_path: Mapped[str] = mapped_column(String(500))
    thumbnail_path: Mapped[str] = mapped_column(String(500), default="")

    room_template = relationship("RoomTemplate", back_populates="reference_images")
    reference_set = relationship("ReferenceImageSet", back_populates="images")
