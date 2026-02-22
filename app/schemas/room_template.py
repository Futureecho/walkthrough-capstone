from __future__ import annotations
from datetime import datetime
from typing import Any
from pydantic import BaseModel


class PositionItem(BaseModel):
    label: str
    hint: str


class RoomTemplateCreate(BaseModel):
    name: str
    display_order: int = 0
    positions: list[PositionItem] = []
    capture_mode: str = "traditional"


class RoomTemplateRead(BaseModel):
    id: str
    property_id: str
    name: str
    display_order: int
    positions: list[dict[str, Any]]
    capture_mode: str = "traditional"
    created_at: datetime

    model_config = {"from_attributes": True}


class RoomTemplateUpdate(BaseModel):
    name: str | None = None
    display_order: int | None = None
    positions: list[PositionItem] | None = None
    capture_mode: str | None = None
