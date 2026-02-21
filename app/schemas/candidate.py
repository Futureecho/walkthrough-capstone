from __future__ import annotations
from datetime import datetime
from typing import Any
from pydantic import BaseModel


class CandidateRead(BaseModel):
    id: str
    comparison_id: str
    region_json: dict[str, Any] | None = None
    confidence: float
    reason_codes: list[str] | None = None
    crop_path: str
    followup_status: str
    tenant_response: str
    tenant_comment: str
    owner_accepted: bool | None = None
    repair_cost: float = 0.0
    owner_notes: str = ""
    created_at: datetime

    model_config = {"from_attributes": True}


class CandidateResponse(BaseModel):
    response: str  # confirm | disagree
    comment: str = ""


class CandidateOwnerUpdate(BaseModel):
    owner_accepted: bool | None = None
    repair_cost: float | None = None
    owner_notes: str | None = None
