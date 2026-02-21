import pytest
import numpy as np
from PIL import Image

from app.services.quality_checks import (
    compute_blur_score,
    compute_darkness_score,
    compute_sharpness_score,
    compute_all_metrics,
)


@pytest.fixture
def gray_image(tmpdir):
    """Create a solid gray 100x100 test image and return its path."""
    img = Image.new("RGB", (100, 100), color=(128, 128, 128))
    path = str(tmpdir / "test_gray.png")
    img.save(path)
    return path


def test_compute_blur_score_returns_float(gray_image):
    score = compute_blur_score(gray_image)
    assert isinstance(score, float)


def test_compute_darkness_score_returns_float_in_range(gray_image):
    score = compute_darkness_score(gray_image)
    assert isinstance(score, float)
    assert 0.0 <= score <= 255.0


def test_compute_sharpness_score_returns_float(gray_image):
    score = compute_sharpness_score(gray_image)
    assert isinstance(score, float)


def test_compute_all_metrics_returns_dict_with_keys(gray_image):
    metrics = compute_all_metrics(gray_image)
    assert isinstance(metrics, dict)
    assert "blur_score" in metrics
    assert "darkness_score" in metrics
    assert "sharpness_score" in metrics
