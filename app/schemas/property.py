from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel


class PropertyCreate(BaseModel):
    label: str
    rooms: list[str] = []
    address: str = ""


class PropertyRead(BaseModel):
    id: str
    label: str
    rooms: list[str]
    address: str = ""
    owner_id: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
