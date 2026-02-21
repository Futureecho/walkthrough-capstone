from __future__ import annotations

from sqlalchemy import String, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ULIDMixin


class Annotation(Base, ULIDMixin):
    __tablename__ = "annotations"

    capture_image_id: Mapped[str] = mapped_column(String(26), ForeignKey("capture_images.id"))
    region_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")

    capture_image = relationship("CaptureImage", back_populates="annotations")
