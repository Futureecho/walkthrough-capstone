from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class ReferenceImageRead(BaseModel):
    id: str
    room_template_id: str
    position_hint: str
    seq: int
    file_path: str
    thumbnail_path: str
    created_at: datetime

    model_config = {"from_attributes": True}
