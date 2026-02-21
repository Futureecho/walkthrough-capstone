"""Tests for the Comparison Agent tools."""

import json
import pytest
import numpy as np

from app.agents.comparison.tools import (
    apply_language_policy,
    parse_analysis_response,
    extract_candidate_regions,
)


# ── apply_language_policy tests ──────────────────────────────────────

def test_language_policy_scrubs_forbidden():
    text = "Damage confirmed in the living room wall"
    forbidden = ["damage confirmed"]
    result = apply_language_policy(text, forbidden, [])
    assert "damage confirmed" not in result.lower()
    assert "candidate difference" in result.lower()


def test_language_policy_scrubs_multiple_forbidden():
    text = "Damage confirmed on ceiling. Clear evidence of water damage visible."
    forbidden = ["damage confirmed", "clear evidence"]
    result = apply_language_policy(text, forbidden, [])
    assert "damage confirmed" not in result.lower()
    assert "clear evidence" not in result.lower()


def test_language_policy_preserves_clean_text():
    text = "A candidate difference was observed near the window frame."
    forbidden = ["damage confirmed"]
    result = apply_language_policy(text, forbidden, [])
    assert "candidate difference" in result.lower()
    assert "window frame" in result.lower()


def test_language_policy_case_insensitive():
    text = "DAMAGE CONFIRMED on the baseboard"
    forbidden = ["damage confirmed"]
    result = apply_language_policy(text, forbidden, [])
    assert "damage confirmed" not in result.lower()


def test_language_policy_with_required_terms():
    text = "Some differences noted in the hallway."
    forbidden = []
    required = ["candidate difference"]
    result = apply_language_policy(text, forbidden, required)
    assert isinstance(result, str)


# ── parse_analysis_response tests ────────────────────────────────────

def test_parse_analysis_response_valid_json():
    raw = json.dumps({
        "analysis": "scuff mark on wall",
        "confidence": 0.7,
        "reason_codes": ["scuff"],
        "needs_closeup": True,
    })
    result = parse_analysis_response(raw)
    assert isinstance(result, dict)
    assert "analysis" in result
    assert result["confidence"] == 0.7


def test_parse_analysis_response_json_in_code_fence():
    payload = {
        "analysis": "No differences found.",
        "confidence": 0.1,
        "reason_codes": [],
        "needs_closeup": False,
    }
    raw = f"```json\n{json.dumps(payload)}\n```"
    result = parse_analysis_response(raw)
    assert isinstance(result, dict)
    assert result["reason_codes"] == []


def test_parse_analysis_response_invalid_json():
    raw = "I found some stuff but this isn't JSON"
    result = parse_analysis_response(raw)
    assert isinstance(result, dict)
    assert "analysis" in result
    assert result["confidence"] == 0.3


def test_parse_analysis_response_empty_string():
    result = parse_analysis_response("")
    assert isinstance(result, dict)
    assert "analysis" in result


# ── extract_candidate_regions tests ──────────────────────────────────

def test_extract_regions_from_synthetic_diff():
    diff = np.zeros((200, 200), dtype=np.uint8)
    diff[50:100, 50:100] = 200
    regions = extract_candidate_regions(diff, threshold=0.1, min_area=100)
    assert len(regions) >= 1
    assert regions[0]["w"] > 0


def test_extract_regions_empty_diff():
    diff = np.zeros((200, 200), dtype=np.uint8)
    regions = extract_candidate_regions(diff, threshold=0.1, min_area=100)
    assert len(regions) == 0


def test_extract_regions_full_diff():
    diff = np.full((200, 200), 200, dtype=np.uint8)
    regions = extract_candidate_regions(diff, threshold=0.1, min_area=100)
    assert len(regions) >= 1


def test_extract_regions_small_noise_filtered():
    diff = np.zeros((200, 200), dtype=np.uint8)
    diff[10:13, 10:13] = 200  # 3x3 = 9 pixels, below min_area=100
    regions = extract_candidate_regions(diff, threshold=0.1, min_area=100)
    assert len(regions) == 0


def test_extract_regions_multiple_blobs():
    diff = np.zeros((200, 200), dtype=np.uint8)
    diff[10:40, 10:40] = 200
    diff[120:160, 120:160] = 200
    regions = extract_candidate_regions(diff, threshold=0.1, min_area=100)
    assert len(regions) == 2


def test_extract_regions_returns_bounding_boxes():
    diff = np.zeros((200, 200), dtype=np.uint8)
    diff[50:100, 50:100] = 200
    regions = extract_candidate_regions(diff, threshold=0.1, min_area=100)
    assert len(regions) >= 1
    for r in regions:
        assert "x" in r and "y" in r and "w" in r and "h" in r
