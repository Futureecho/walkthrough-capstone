from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel
from app.schemas.capture import CaptureRead


class SessionCreate(BaseModel):
    type: str  # move_in | move_out
    tenant_name: str = ""
    tenant_name_2: str = ""


class SessionRead(BaseModel):
    id: str
    property_id: str
    type: str
    tenant_name: str
    tenant_name_2: str = ""
    report_status: str = "draft"
    review_flag: str | None = None
    created_at: datetime
    captures: list[CaptureRead] = []

    model_config = {"from_attributes": True}
