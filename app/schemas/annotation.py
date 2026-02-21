from __future__ import annotations
from datetime import datetime
from typing import Any
from pydantic import BaseModel


class AnnotationCreate(BaseModel):
    capture_image_id: str
    region_json: dict[str, Any] | None = None
    note: str = ""


class AnnotationRead(BaseModel):
    id: str
    capture_image_id: str
    region_json: dict[str, Any] | None = None
    note: str
    created_at: datetime

    model_config = {"from_attributes": True}
