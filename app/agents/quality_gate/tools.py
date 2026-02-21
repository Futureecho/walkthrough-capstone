"""Quality Gate Agent tools — wrapped CV functions for LangGraph."""

from __future__ import annotations

from app.services.quality_checks import (
    compute_blur_score,
    compute_darkness_score,
    compute_sharpness_score,
)


def compute_blur(file_path: str) -> float:
    """Compute Laplacian variance blur score. Higher = sharper."""
    return compute_blur_score(file_path)


def compute_darkness(file_path: str) -> float:
    """Compute mean brightness. Low = too dark."""
    return compute_darkness_score(file_path)


def compute_sharpness(file_path: str) -> float:
    """Compute Tenengrad sharpness score. Higher = sharper."""
    return compute_sharpness_score(file_path)


def decide_quality(
    blur: float, darkness: float, sharpness: float,
    blur_threshold: float, darkness_threshold: float,
    sharpness_threshold: float, borderline_margin: float,
) -> str:
    """Deterministic quality decision: accepted | rejected | borderline."""
    # Hard failures
    if blur < blur_threshold - borderline_margin:
        return "rejected"
    if darkness < darkness_threshold - borderline_margin:
        return "rejected"
    if sharpness < sharpness_threshold - borderline_margin:
        return "rejected"

    # Clear passes
    if (blur >= blur_threshold and
            darkness >= darkness_threshold and
            sharpness >= sharpness_threshold):
        return "accepted"

    # Everything in between = borderline
    return "borderline"
