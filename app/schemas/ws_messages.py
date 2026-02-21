from __future__ import annotations
from typing import Any
from pydantic import BaseModel


class WSMessage(BaseModel):
    event: str  # quality_update | coverage_update | comparison_update | error
    capture_id: str = ""
    image_id: str = ""
    data: dict[str, Any] = {}
