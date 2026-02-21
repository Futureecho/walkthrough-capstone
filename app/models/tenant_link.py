from __future__ import annotations

from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ULIDMixin


class TenantLink(Base, ULIDMixin):
    __tablename__ = "tenant_links"

    session_id: Mapped[str] = mapped_column(String(26), ForeignKey("sessions.id"))
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    session = relationship("Session", back_populates="tenant_links")
