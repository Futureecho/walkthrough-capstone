"""Image storage: save originals, generate thumbnails, path helpers.

Images are stored per company: data/companies/{company_id}/images/{capture_id}/...
Files are Fernet-encrypted at rest with .enc suffix.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from PIL import Image
import io

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
    thumb_path = thumb_dir / filename

    # Generate thumbnail from raw bytes
    img = Image.open(io.BytesIO(data))
    thumb_buf = io.BytesIO()
    img_copy = img.copy()
    img_copy.thumbnail(_THUMB_SIZE)
    img_copy.save(thumb_buf, "JPEG", quality=85)
    thumb_bytes = thumb_buf.getvalue()

    # Encrypt and save with .enc suffix
    try:
        from app.services.encryption import encrypt_bytes
        enc_orig = orig_dir / f"{filename}.enc"
        enc_thumb = thumb_dir / f"{filename}.enc"
        enc_orig.write_bytes(encrypt_bytes(data))
        enc_thumb.write_bytes(encrypt_bytes(thumb_bytes))
        return str(enc_orig), str(enc_thumb)
    except RuntimeError:
        # FERNET_KEY not set — save plaintext (dev mode)
        orig_path.write_bytes(data)
        thumb_path.write_bytes(thumb_bytes)
        return str(orig_path), str(thumb_path)


async def save_image(data: bytes, capture_id: str, seq: int, ext: str = ".jpg", company_id: str | None = None) -> tuple[str, str]:
    """Save original image and create thumbnail. Returns (orig_path, thumb_path)."""
    return await asyncio.to_thread(_save_sync, data, capture_id, seq, ext, company_id)


def read_image_sync(file_path: str) -> bytes:
    """Read an image file, decrypting if it's a .enc file.

    Tries .enc version first, falls back to plaintext.
    """
    p = Path(file_path)

    # If path already ends in .enc, read and decrypt
    if p.suffix == ".enc" and p.exists():
        from app.services.encryption import decrypt_bytes
        return decrypt_bytes(p.read_bytes())

    # Try .enc version of the path
    enc_path = Path(str(p) + ".enc")
    if enc_path.exists():
        from app.services.encryption import decrypt_bytes
        return decrypt_bytes(enc_path.read_bytes())

    # Fall back to plaintext
    if p.exists():
        return p.read_bytes()

    raise FileNotFoundError(f"Image not found: {file_path}")


async def read_image(file_path: str) -> bytes:
    """Async wrapper for read_image_sync."""
    return await asyncio.to_thread(read_image_sync, file_path)


def get_image_path(capture_id: str, seq: int, ext: str = ".jpg", company_id: str | None = None) -> Path:
    return _get_base(company_id) / capture_id / "originals" / f"{seq:03d}{ext}"


def get_thumbnail_path(capture_id: str, seq: int, ext: str = ".jpg", company_id: str | None = None) -> Path:
    return _get_base(company_id) / capture_id / "thumbnails" / f"{seq:03d}{ext}"
