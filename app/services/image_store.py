"""Image storage: save originals, generate thumbnails, path helpers."""

from __future__ import annotations

import asyncio
from pathlib import Path

from PIL import Image

from app.config import get_settings

_settings = get_settings()
_BASE = Path(_settings.image_store.base_dir)
_THUMB_SIZE = _settings.image_store.thumbnail_size


def _ensure_dirs(capture_id: str) -> tuple[Path, Path]:
    orig_dir = _BASE / capture_id / "originals"
    thumb_dir = _BASE / capture_id / "thumbnails"
    orig_dir.mkdir(parents=True, exist_ok=True)
    thumb_dir.mkdir(parents=True, exist_ok=True)
    return orig_dir, thumb_dir


def _save_sync(data: bytes, capture_id: str, seq: int, ext: str = ".jpg") -> tuple[str, str]:
    orig_dir, thumb_dir = _ensure_dirs(capture_id)
    filename = f"{seq:03d}{ext}"

    orig_path = orig_dir / filename
    orig_path.write_bytes(data)

    # Generate thumbnail
    thumb_path = thumb_dir / filename
    img = Image.open(orig_path)
    img.thumbnail(_THUMB_SIZE)
    img.save(thumb_path, "JPEG", quality=85)

    return str(orig_path), str(thumb_path)


async def save_image(data: bytes, capture_id: str, seq: int, ext: str = ".jpg") -> tuple[str, str]:
    """Save original image and create thumbnail. Returns (orig_path, thumb_path)."""
    return await asyncio.to_thread(_save_sync, data, capture_id, seq, ext)


def get_image_path(capture_id: str, seq: int, ext: str = ".jpg") -> Path:
    return _BASE / capture_id / "originals" / f"{seq:03d}{ext}"


def get_thumbnail_path(capture_id: str, seq: int, ext: str = ".jpg") -> Path:
    return _BASE / capture_id / "thumbnails" / f"{seq:03d}{ext}"
