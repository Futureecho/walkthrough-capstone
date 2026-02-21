from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel


class TenantLinkCreate(BaseModel):
    session_type: str  # move_in | move_out
    tenant_name: str = ""
    tenant_name_2: str = ""
    duration_days: int = 7


class TenantLinkRead(BaseModel):
    id: str
    session_id: str
    token: str
    expires_at: datetime
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
