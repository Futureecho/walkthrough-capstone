from __future__ import annotations

from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ULIDMixin
from app.models.encrypted_type import EncryptedString


class Session(Base, ULIDMixin):
    __tablename__ = "sessions"

    property_id: Mapped[str] = mapped_column(String(26), ForeignKey("properties.id"))
    type: Mapped[str] = mapped_column(String(20))  # move_in | move_out
    tenant_name: Mapped[str] = mapped_column(EncryptedString(255), default="")
    tenant_name_2: Mapped[str] = mapped_column(EncryptedString(255), default="")
    report_status: Mapped[str] = mapped_column(String(30), default="draft")
    review_flag: Mapped[str | None] = mapped_column(String(30), nullable=True, default=None)

    property = relationship("Property", back_populates="sessions")
    captures = relationship("Capture", back_populates="session", lazy="selectin")
    tenant_links = relationship("TenantLink", back_populates="session", lazy="selectin")
