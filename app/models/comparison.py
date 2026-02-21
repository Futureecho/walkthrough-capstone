from __future__ import annotations

from sqlalchemy import String, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ULIDMixin


class Comparison(Base, ULIDMixin):
    __tablename__ = "comparisons"

    room: Mapped[str] = mapped_column(String(100))
    move_in_capture_id: Mapped[str] = mapped_column(String(26), ForeignKey("captures.id"))
    move_out_capture_id: Mapped[str] = mapped_column(String(26), ForeignKey("captures.id"))
    status: Mapped[str] = mapped_column(String(30), default="pending")  # pending | processing | complete
    diff_data_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    move_in_capture = relationship("Capture", foreign_keys=[move_in_capture_id])
    move_out_capture = relationship("Capture", foreign_keys=[move_out_capture_id])
    candidates = relationship("Candidate", back_populates="comparison", lazy="selectin")
