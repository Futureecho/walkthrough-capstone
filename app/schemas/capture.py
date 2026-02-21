from __future__ import annotations
from datetime import datetime
from typing import Any
from pydantic import BaseModel
from app.schemas.capture_image import CaptureImageRead


class CaptureCreate(BaseModel):
    session_id: str
    room: str
    device_meta: dict[str, Any] | None = None


class CaptureRead(BaseModel):
    id: str
    session_id: str
    room: str
    status: str
    device_meta: dict[str, Any] | None = None
    metrics_json: dict[str, Any] | None = None
    coverage_json: dict[str, Any] | None = None
    created_at: datetime
    images: list[CaptureImageRead] = []

    model_config = {"from_attributes": True}


class CaptureStatus(BaseModel):
    id: str
    status: str
    metrics_json: dict[str, Any] | None = None
    coverage_json: dict[str, Any] | None = None
    image_count: int = 0
