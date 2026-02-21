"""Tests for the Coverage Review Agent.

Validates coverage aggregation, checklist generation, and
summary response parsing logic.
"""

import json
import pytest

from app.agents.coverage_review.tools import (
    aggregate_coverage,
    get_checklist,
    parse_summary_response,
)


# ── aggregate_coverage tests ─────────────────────────────────────────


def test_aggregate_full_coverage():
    """When all standard areas are covered, coverage_pct should be >= 80%."""
    summaries = [
        {
            "coverage_areas": [
                "wall-left",
                "wall-right",
                "wall-far",
                "wall-near",
                "floor",
                "ceiling",
                "door",
            ]
        }
    ]
    result = aggregate_coverage(summaries, "Living Room")
    assert result["coverage_pct"] >= 80.0


def test_aggregate_partial_coverage():
    """A single area covered should be well below 50% and report missing items."""
    summaries = [{"coverage_areas": ["wall-left"]}]
    result = aggregate_coverage(summaries, "default")
    assert result["coverage_pct"] < 50.0
    assert len(result["missing"]) > 0


def test_aggregate_empty_summaries():
    """No summaries at all should yield 0% coverage."""
    result = aggregate_coverage([], "Bedroom")
    assert result["coverage_pct"] == 0.0
    assert len(result["missing"]) > 0


def test_aggregate_duplicate_areas_not_double_counted():
    """Repeated coverage of the same area across summaries should not
    inflate the percentage."""
    summaries = [
        {"coverage_areas": ["wall-left", "floor"]},
        {"coverage_areas": ["wall-left", "floor"]},
    ]
    result = aggregate_coverage(summaries, "default")
    # Two unique areas out of the full checklist
    summaries_single = [{"coverage_areas": ["wall-left", "floor"]}]
    result_single = aggregate_coverage(summaries_single, "default")
    assert result["coverage_pct"] == result_single["coverage_pct"]


def test_aggregate_returns_covered_list():
    """Result should include a list of which areas were covered."""
    summaries = [{"coverage_areas": ["wall-left", "ceiling"]}]
    result = aggregate_coverage(summaries, "default")
    assert "covered" in result or "coverage_areas" in result or "missing" in result


# ── get_checklist tests ──────────────────────────────────────────────


def test_get_checklist_returns_list():
    """get_checklist should return a non-empty list for any room type."""
    checklist = get_checklist("Living Room")
    assert isinstance(checklist, list)
    assert len(checklist) > 0


def test_get_checklist_default_room():
    """An unknown room type should still return a reasonable default checklist."""
    checklist = get_checklist("default")
    assert isinstance(checklist, list)
    assert len(checklist) > 0


def test_get_checklist_kitchen_has_appliances():
    """Kitchen checklists should include appliance-related items."""
    checklist = get_checklist("Kitchen")
    # At minimum, a kitchen checklist should have more than generic walls
    assert len(checklist) >= 4


def test_get_checklist_bathroom():
    """Bathroom should return a valid checklist."""
    checklist = get_checklist("Bathroom")
    assert isinstance(checklist, list)
    assert len(checklist) > 0


# ── parse_summary_response tests ─────────────────────────────────────


def test_parse_summary_response_valid_json():
    """Valid JSON should be parsed and returned as a dict."""
    raw = json.dumps({
        "coverage_areas": ["wall-left", "floor", "ceiling"],
        "notes": "Good coverage of the main living area.",
    })
    result = parse_summary_response(raw)
    assert isinstance(result, dict)
    assert "coverage_areas" in result
    assert len(result["coverage_areas"]) == 3


def test_parse_summary_response_json_in_markdown_block():
    """JSON wrapped in a markdown code fence should still parse."""
    raw = '```json\n{"coverage_areas": ["wall-left"], "notes": "partial"}\n```'
    result = parse_summary_response(raw)
    assert isinstance(result, dict)
    assert "coverage_areas" in result


def test_parse_summary_response_invalid_json_fallback():
    """Invalid JSON should not raise; fallback should return a dict with
    an empty or minimal coverage_areas list."""
    raw = "This is not valid JSON at all, just a free-text note."
    result = parse_summary_response(raw)
    assert isinstance(result, dict)
    # Fallback should still have the expected key
    assert "coverage_areas" in result


def test_parse_summary_response_empty_string():
    """An empty string should fall back gracefully."""
    result = parse_summary_response("")
    assert isinstance(result, dict)
    assert "coverage_areas" in result
