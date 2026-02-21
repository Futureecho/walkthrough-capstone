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


def explain_quality(
    blur: float, darkness: float, sharpness: float,
    blur_threshold: float, darkness_threshold: float,
    sharpness_threshold: float,
) -> list[dict]:
    """Return human-friendly rejection reasons with tips.

    Each entry: {"issue": str, "detail": str, "tip": str}
    """
    reasons = []
    if blur < blur_threshold:
        reasons.append({
            "issue": "Too blurry",
            "detail": f"Sharpness score {blur:.0f} is below the minimum {blur_threshold:.0f}.",
            "tip": "Hold your phone steady or brace it against a surface. Tap the screen to focus before shooting.",
        })
    if darkness < darkness_threshold:
        reasons.append({
            "issue": "Too dark",
            "detail": f"Brightness level {darkness:.0f} is below the minimum {darkness_threshold:.0f}.",
            "tip": "Turn on the room lights or open blinds. If needed, enable your phone's flash.",
        })
    if sharpness < sharpness_threshold:
        reasons.append({
            "issue": "Low detail",
            "detail": f"Detail score {sharpness:.0f} is below the minimum {sharpness_threshold:.0f}.",
            "tip": "Move closer or make sure the camera lens is clean. Avoid shooting through glass or screens.",
        })
    return reasons
