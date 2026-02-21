from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel


class OwnerLogin(BaseModel):
    username: str
    password: str


class OwnerRead(BaseModel):
    id: str
    username: str
    created_at: datetime

    model_config = {"from_attributes": True}
