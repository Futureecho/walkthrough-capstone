"""Image storage: save originals, generate thumbnails, path helpers.

Images are stored per company: data/companies/{company_id}/images/{capture_id}/...
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from PIL import Image

from app.config import get_settings

_settings = get_settings()
_THUMB_SIZE = _settings.image_store.thumbnail_size


def _get_base(company_id: str | None = None) -> Path:
    if company_id:
        return Path(f"data/companies/{company_id}/images")
    # Fallback for legacy/migration
    return Path(_settings.image_store.base_dir)


def _ensure_dirs(capture_id: str, company_id: str | None = None) -> tuple[Path, Path]:
    base = _get_base(company_id)
    orig_dir = base / capture_id / "originals"
    thumb_dir = base / capture_id / "thumbnails"
    orig_dir.mkdir(parents=True, exist_ok=True)
    thumb_dir.mkdir(parents=True, exist_ok=True)
    return orig_dir, thumb_dir


def _save_sync(data: bytes, capture_id: str, seq: int, ext: str = ".jpg", company_id: str | None = None) -> tuple[str, str]:
    orig_dir, thumb_dir = _ensure_dirs(capture_id, company_id)
    filename = f"{seq:03d}{ext}"

    orig_path = orig_dir / filename
    orig_path.write_bytes(data)

    # Generate thumbnail
    thumb_path = thumb_dir / filename
    img = Image.open(orig_path)
    img.thumbnail(_THUMB_SIZE)
    img.save(thumb_path, "JPEG", quality=85)

    return str(orig_path), str(thumb_path)


async def save_image(data: bytes, capture_id: str, seq: int, ext: str = ".jpg", company_id: str | None = None) -> tuple[str, str]:
    """Save original image and create thumbnail. Returns (orig_path, thumb_path)."""
    return await asyncio.to_thread(_save_sync, data, capture_id, seq, ext, company_id)


def get_image_path(capture_id: str, seq: int, ext: str = ".jpg", company_id: str | None = None) -> Path:
    return _get_base(company_id) / capture_id / "originals" / f"{seq:03d}{ext}"


def get_thumbnail_path(capture_id: str, seq: int, ext: str = ".jpg", company_id: str | None = None) -> Path:
    return _get_base(company_id) / capture_id / "thumbnails" / f"{seq:03d}{ext}"
