from __future__ import annotations

from sqlalchemy import String, Integer, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ULIDMixin


class CaptureImage(Base, ULIDMixin):
    __tablename__ = "capture_images"

    capture_id: Mapped[str] = mapped_column(String(26), ForeignKey("captures.id"))
    seq: Mapped[int] = mapped_column(Integer)
    file_path: Mapped[str] = mapped_column(String(500))
    thumbnail_path: Mapped[str] = mapped_column(String(500), default="")
    orientation_hint: Mapped[str] = mapped_column(String(50), default="")
    quality_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    capture = relationship("Capture", back_populates="images")
    annotations = relationship("Annotation", back_populates="capture_image", lazy="selectin")
