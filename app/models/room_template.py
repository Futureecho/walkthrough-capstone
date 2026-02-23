from __future__ import annotations

from typing import Optional

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
    active_ref_set_id: Mapped[Optional[str]] = mapped_column(
        String(26), ForeignKey("reference_image_sets.id", ondelete="SET NULL"),
        nullable=True,
    )

    property = relationship("Property", back_populates="room_templates")
    reference_images = relationship(
        "ReferenceImage", back_populates="room_template",
        lazy="selectin", cascade="all, delete-orphan",
    )
    reference_sets = relationship(
        "ReferenceImageSet", back_populates="room_template",
        lazy="selectin", cascade="all, delete-orphan",
        foreign_keys="ReferenceImageSet.room_template_id",
    )
    active_ref_set = relationship(
        "ReferenceImageSet",
        foreign_keys=[active_ref_set_id],
        post_update=True,
    )
