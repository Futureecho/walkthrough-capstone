from __future__ import annotations

from sqlalchemy import String, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ULIDMixin


class Property(Base, ULIDMixin):
    __tablename__ = "properties"

    label: Mapped[str] = mapped_column(String(255))
    rooms: Mapped[list] = mapped_column(JSON, default=list)
    address: Mapped[str] = mapped_column(String(500), default="")

    sessions = relationship("Session", back_populates="property", lazy="selectin")
    room_templates = relationship("RoomTemplate", back_populates="property", lazy="selectin",
                                  order_by="RoomTemplate.display_order")
