from __future__ import annotations
from datetime import datetime
from typing import Any
from pydantic import BaseModel
from app.schemas.candidate import CandidateRead


class ComparisonRead(BaseModel):
    id: str
    room: str
    move_in_capture_id: str
    move_out_capture_id: str
    status: str
    diff_data_json: dict[str, Any] | None = None
    created_at: datetime
    candidates: list[CandidateRead] = []

    model_config = {"from_attributes": True}
