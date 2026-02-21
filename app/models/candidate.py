from __future__ import annotations

from sqlalchemy import String, Float, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ULIDMixin


class Candidate(Base, ULIDMixin):
    __tablename__ = "candidates"

    comparison_id: Mapped[str] = mapped_column(String(26), ForeignKey("comparisons.id"))
    region_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    reason_codes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    crop_path: Mapped[str] = mapped_column(String(500), default="")
    followup_status: Mapped[str] = mapped_column(String(30), default="pending")  # pending | responded | closeup_uploaded
    tenant_response: Mapped[str] = mapped_column(String(30), default="")  # confirm | disagree | ""
    tenant_comment: Mapped[str] = mapped_column(Text, default="")

    comparison = relationship("Comparison", back_populates="candidates")
