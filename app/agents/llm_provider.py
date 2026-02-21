"""Abstract LLM provider with OpenAI and Anthropic adapters."""

from __future__ import annotations

import base64
from abc import ABC, abstractmethod
from pathlib import Path

from app.config import get_settings


class LLMProvider(ABC):
    """Abstract interface for vision-capable LLM calls."""

    @abstractmethod
    async def analyze_image(self, image_path: str, prompt: str) -> str:
        """Send an image + prompt to the LLM, return text response."""
        ...

    @abstractmethod
    async def analyze_images(self, image_paths: list[str], prompt: str) -> str:
        """Send multiple images + prompt to the LLM, return text response."""
        ...

    @abstractmethod
    async def chat(self, prompt: str) -> str:
        """Text-only chat completion."""
        ...


def _encode_image(path: str) -> str:
    """Base64-encode an image file."""
    data = Path(path).read_bytes()
    return base64.standard_b64encode(data).decode("utf-8")


def _media_type(path: str) -> str:
    ext = Path(path).suffix.lower()
    return {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "webp": "image/webp", "gif": "image/gif"}.get(ext.lstrip("."), "image/jpeg")


class OpenAIProvider(LLMProvider):
    """OpenAI GPT-4o vision provider."""

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def analyze_image(self, image_path: str, prompt: str) -> str:
        b64 = _encode_image(image_path)
        mt = _media_type(image_path)
        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mt};base64,{b64}"}},
                ],
            }],
            max_tokens=1024,
        )
        return resp.choices[0].message.content

    async def analyze_images(self, image_paths: list[str], prompt: str) -> str:
        content = [{"type": "text", "text": prompt}]
        for path in image_paths:
            b64 = _encode_image(path)
            mt = _media_type(path)
            content.append({"type": "image_url", "image_url": {"url": f"data:{mt};base64,{b64}"}})
        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": content}],
            max_tokens=2048,
        )
        return resp.choices[0].message.content

    async def chat(self, prompt: str) -> str:
        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
        )
        return resp.choices[0].message.content


class AnthropicProvider(LLMProvider):
    """Anthropic Claude vision provider."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        from anthropic import AsyncAnthropic
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model

    async def analyze_image(self, image_path: str, prompt: str) -> str:
        b64 = _encode_image(image_path)
        mt = _media_type(image_path)
        resp = await self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": mt, "data": b64}},
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        return resp.content[0].text

    async def analyze_images(self, image_paths: list[str], prompt: str) -> str:
        content = []
        for path in image_paths:
            b64 = _encode_image(path)
            mt = _media_type(path)
            content.append({"type": "image", "source": {"type": "base64", "media_type": mt, "data": b64}})
        content.append({"type": "text", "text": prompt})
        resp = await self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            messages=[{"role": "user", "content": content}],
        )
        return resp.content[0].text

    async def chat(self, prompt: str) -> str:
        resp = await self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt}]}],
        )
        return resp.content[0].text


def get_llm_provider() -> LLMProvider:
    """Factory: returns OpenAI provider if key available, else Anthropic."""
    settings = get_settings()
    if settings.openai_api_key:
        return OpenAIProvider(settings.openai_api_key)
    if settings.anthropic_api_key:
        return AnthropicProvider(settings.anthropic_api_key)
    raise RuntimeError("No LLM API key configured. Set OPENAI_API_KEY or ANTHROPIC_API_KEY.")
