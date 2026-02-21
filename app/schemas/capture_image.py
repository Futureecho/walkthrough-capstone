from __future__ import annotations
from datetime import datetime
from typing import Any
from pydantic import BaseModel


class CaptureImageRead(BaseModel):
    id: str
    capture_id: str
    seq: int
    file_path: str
    thumbnail_path: str
    orientation_hint: str
    quality_json: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
