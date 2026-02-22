"""Work order model — dispatched to technicians for repairs."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Float, ForeignKey, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ULIDMixin


class WorkOrder(Base, ULIDMixin):
    __tablename__ = "work_orders"

    session_id: Mapped[str] = mapped_column(String(26), ForeignKey("sessions.id"))
    technician_id: Mapped[str] = mapped_column(String(26), ForeignKey("technicians.id"))
    contact_name: Mapped[str] = mapped_column(String(200), default="")
    contact_phone: Mapped[str] = mapped_column(String(50), default="")
    order_type: Mapped[str] = mapped_column(String(30))  # nte | call_estimate | proceed
    nte_amount: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | dispatched
    included_concern_ids: Mapped[list] = mapped_column(JSON, default=list)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

    technician = relationship("Technician")
    session = relationship("Session", back_populates="work_orders")
