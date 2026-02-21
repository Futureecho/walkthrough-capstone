from __future__ import annotations

from sqlalchemy import String, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ULIDMixin


class Capture(Base, ULIDMixin):
    __tablename__ = "captures"

    session_id: Mapped[str] = mapped_column(String(26), ForeignKey("sessions.id"))
    room: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), default="pending")  # pending | processing | passed | failed
    device_meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metrics_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    coverage_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    session = relationship("Session", back_populates="captures")
    images = relationship("CaptureImage", back_populates="capture", lazy="selectin", order_by="CaptureImage.seq")
