"""Company settings schemas (renamed from owner_settings)."""

from __future__ import annotations
from pydantic import BaseModel, field_validator


class CompanySettingsRead(BaseModel):
    id: str
    llm_provider: str
    openai_api_key_set: bool = False
    anthropic_api_key_set: bool = False
    gemini_api_key_set: bool = False
    grok_api_key_set: bool = False
    default_link_days: int

    model_config = {"from_attributes": True}


class CompanySettingsUpdate(BaseModel):
    llm_provider: str | None = None
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    gemini_api_key: str | None = None
    grok_api_key: str | None = None
    default_link_days: int | None = None
    approval_email: str | None = None

    @field_validator("llm_provider")
    @classmethod
    def validate_llm_provider(cls, v: str | None) -> str | None:
        if v is not None and v not in ("openai", "anthropic", "gemini", "grok", "none"):
            raise ValueError(f"Invalid llm_provider: {v}")
        return v


# Backwards-compat aliases
OwnerSettingsRead = CompanySettingsRead
OwnerSettingsUpdate = CompanySettingsUpdate
