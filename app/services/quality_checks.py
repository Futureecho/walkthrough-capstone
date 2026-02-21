"""Classical CV quality checks: blur, darkness, sharpness."""

from __future__ import annotations

import asyncio
from pathlib import Path

import cv2
import numpy as np


def _load_grayscale(file_path: str) -> np.ndarray:
    img = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError(f"Cannot read image: {file_path}")
    return img


def compute_blur_score(file_path: str) -> float:
    """Laplacian variance — higher = sharper. Low = blurry."""
    gray = _load_grayscale(file_path)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def compute_darkness_score(file_path: str) -> float:
    """Mean brightness (0-255). Low = too dark."""
    gray = _load_grayscale(file_path)
    return float(np.mean(gray))


def compute_sharpness_score(file_path: str) -> float:
    """Tenengrad variance (Sobel gradient magnitude). Higher = sharper."""
    gray = _load_grayscale(file_path)
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    magnitude = np.sqrt(gx**2 + gy**2)
    return float(np.mean(magnitude))


def compute_all_metrics(file_path: str) -> dict:
    """Run all quality checks, return scores dict."""
    return {
        "blur_score": compute_blur_score(file_path),
        "darkness_score": compute_darkness_score(file_path),
        "sharpness_score": compute_sharpness_score(file_path),
    }


async def compute_all_metrics_async(file_path: str) -> dict:
    """Async wrapper for compute_all_metrics."""
    return await asyncio.to_thread(compute_all_metrics, file_path)
