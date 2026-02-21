from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ULIDMixin


class Owner(Base, ULIDMixin):
    __tablename__ = "owners"

    username: Mapped[str] = mapped_column(String(100), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    password_hint: Mapped[str] = mapped_column(String(255), default="")

    settings = relationship("OwnerSettings", back_populates="owner", uselist=False, lazy="selectin")
    properties = relationship("Property", back_populates="owner", lazy="selectin")
