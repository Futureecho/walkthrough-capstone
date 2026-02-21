"""Comparison Agent tools — CV operations for image comparison."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim

logger = logging.getLogger(__name__)


def normalize_exposure(img1_path: str, img2_path: str) -> tuple[np.ndarray, np.ndarray]:
    """Histogram-normalize two images for fair comparison."""
    img1 = cv2.imread(img1_path)
    img2 = cv2.imread(img2_path)

    if img1 is None or img2 is None:
        raise ValueError(f"Cannot read images: {img1_path}, {img2_path}")

    # Resize to common dimensions
    h = min(img1.shape[0], img2.shape[0])
    w = min(img1.shape[1], img2.shape[1])
    img1 = cv2.resize(img1, (w, h))
    img2 = cv2.resize(img2, (w, h))

    # Convert to LAB and normalize L channel
    lab1 = cv2.cvtColor(img1, cv2.COLOR_BGR2LAB)
    lab2 = cv2.cvtColor(img2, cv2.COLOR_BGR2LAB)

    # Match histogram of img2 to img1
    l1, a1, b1 = cv2.split(lab1)
    l2, a2, b2 = cv2.split(lab2)

    # Simple histogram equalization on both
    l1 = cv2.equalizeHist(l1)
    l2 = cv2.equalizeHist(l2)

    norm1 = cv2.merge([l1, a1, b1])
    norm2 = cv2.merge([l2, a2, b2])

    return cv2.cvtColor(norm1, cv2.COLOR_LAB2BGR), cv2.cvtColor(norm2, cv2.COLOR_LAB2BGR)


def compute_structural_diff(img1: np.ndarray, img2: np.ndarray) -> tuple[float, np.ndarray]:
    """Compute SSIM and return (score, diff_map)."""
    gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)

    score, diff = ssim(gray1, gray2, full=True)
    # diff is float64 in [0,1] range; convert to uint8 for contour detection
    diff_uint8 = (255 - (diff * 255)).astype(np.uint8)
    return float(score), diff_uint8


def extract_candidate_regions(
    diff_map: np.ndarray, threshold: float = 0.15, min_area: int = 500
) -> list[dict]:
    """Extract bounding-box regions from SSIM diff map."""
    # Threshold the diff map
    thresh_val = int(threshold * 255)
    _, binary = cv2.threshold(diff_map, thresh_val, 255, cv2.THRESH_BINARY)

    # Morphological cleanup
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

    # Find contours
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    regions = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        # Compute mean diff intensity in the region as a rough confidence proxy
        region_diff = diff_map[y:y+h, x:x+w]
        intensity = float(np.mean(region_diff)) / 255.0
        regions.append({
            "x": int(x), "y": int(y), "w": int(w), "h": int(h),
            "area": int(area),
            "ssim_delta": round(intensity, 3),
        })

    # Sort by area descending
    regions.sort(key=lambda r: r["area"], reverse=True)
    return regions


def crop_region(img: np.ndarray, region: dict, padding: int = 20) -> np.ndarray:
    """Crop a region from an image with padding."""
    h, w = img.shape[:2]
    x1 = max(0, region["x"] - padding)
    y1 = max(0, region["y"] - padding)
    x2 = min(w, region["x"] + region["w"] + padding)
    y2 = min(h, region["y"] + region["h"] + padding)
    return img[y1:y2, x1:x2]


def save_crop(img: np.ndarray, path: str) -> str:
    """Save a cropped image to disk."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(path, img)
    return path


def create_side_by_side(img1: np.ndarray, img2: np.ndarray, region: dict) -> np.ndarray:
    """Create a side-by-side image with the region highlighted."""
    # Draw rectangle on both
    marked1 = img1.copy()
    marked2 = img2.copy()
    color = (0, 0, 255)  # Red
    thickness = 2
    x, y, w, h = region["x"], region["y"], region["w"], region["h"]
    cv2.rectangle(marked1, (x, y), (x+w, y+h), color, thickness)
    cv2.rectangle(marked2, (x, y), (x+w, y+h), color, thickness)

    # Combine side by side
    return np.hstack([marked1, marked2])


def parse_analysis_response(response: str) -> dict:
    """Parse vision LLM analysis response."""
    try:
        text = response.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return json.loads(text)
    except (json.JSONDecodeError, IndexError):
        return {
            "analysis": response[:200],
            "confidence": 0.3,
            "reason_codes": ["other"],
            "needs_closeup": True,
        }


def apply_language_policy(text: str, forbidden: list[str], hedging: list[str]) -> str:
    """Scrub forbidden terms from text."""
    import re
    result = text
    for term in forbidden:
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        result = pattern.sub("candidate difference", result)
    return result
