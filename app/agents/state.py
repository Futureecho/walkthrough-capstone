"""LangGraph TypedDict states for all three agents."""

from __future__ import annotations

from typing import TypedDict, Any


class ImageMetrics(TypedDict):
    image_id: str
    file_path: str
    blur_score: float
    darkness_score: float
    sharpness_score: float
    status: str  # accepted | rejected | borderline
    llm_verdict: str  # "" | accepted | rejected


class QualityGateState(TypedDict):
    capture_id: str
    images: list[dict]  # [{id, file_path, orientation_hint}]
    metrics: list[ImageMetrics]
    borderline_ids: list[str]
    overall_status: str  # passed | failed
    config: dict


class CoverageState(TypedDict):
    capture_id: str
    room: str
    images: list[dict]
    summaries: list[dict]  # [{image_id, summary}] from vision LLM
    coverage: dict  # {coverage_pct, covered, missing, checklist}
    complete: bool
    instructions: list[str]
    config: dict


class ComparisonState(TypedDict):
    comparison_id: str
    room: str
    move_in_images: list[dict]
    move_out_images: list[dict]
    paired_images: list[dict]  # [{move_in_path, move_out_path, region}]
    diff_regions: list[dict]  # [{x, y, w, h, ssim_delta}]
    candidates: list[dict]   # [{region, confidence, reason_codes, analysis}]
    followups: list[dict]
    config: dict
