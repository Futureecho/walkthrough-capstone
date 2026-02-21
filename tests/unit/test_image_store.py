import asyncio
import io
import os
from pathlib import Path

import pytest
from PIL import Image

from app.services import image_store


@pytest.fixture
def jpeg_bytes():
    """Create test JPEG bytes from a solid-color 200x150 image."""
    img = Image.new("RGB", (1920, 1440), color=(70, 130, 180))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def store_dir(tmp_path, monkeypatch):
    """Override image_store._BASE to use a temp directory."""
    base = tmp_path / "image_store"
    base.mkdir()
    monkeypatch.setattr(image_store, "_BASE", base)
    return base


def test_save_image_creates_original_and_thumbnail(jpeg_bytes, store_dir):
    orig, thumb = asyncio.run(image_store.save_image(jpeg_bytes, "test_cap_1", 1))
    assert os.path.isfile(orig)
    assert os.path.isfile(thumb)


def test_thumbnail_smaller_than_original(jpeg_bytes, store_dir):
    orig, thumb = asyncio.run(image_store.save_image(jpeg_bytes, "test_cap_1", 1))
    assert os.path.getsize(thumb) <= os.path.getsize(orig)
