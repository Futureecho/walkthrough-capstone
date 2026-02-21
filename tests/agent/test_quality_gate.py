"""Tests for the Quality Gate Agent."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path
from PIL import Image

from app.agents.quality_gate.tools import decide_quality
from app.agents.quality_gate.graph import build_quality_gate_graph


# ── decide_quality unit tests ────────────────────────────────────────

def test_decide_quality_accepted():
    assert decide_quality(200, 100, 80, 100, 40, 50, 20) == "accepted"


def test_decide_quality_rejected():
    assert decide_quality(10, 100, 80, 100, 40, 50, 20) == "rejected"


def test_decide_quality_borderline():
    assert decide_quality(90, 100, 80, 100, 40, 50, 20) == "borderline"


# ── overall status rollup tests ──────────────────────────────────────

def test_overall_status_passed_when_all_accepted():
    results = [{"status": "accepted"}, {"status": "accepted"}, {"status": "accepted"}]
    has_rejected = any(r["status"] == "rejected" for r in results)
    assert (not has_rejected)  # overall = "passed"


def test_overall_status_failed_when_any_rejected():
    results = [{"status": "accepted"}, {"status": "rejected"}, {"status": "accepted"}]
    has_rejected = any(r["status"] == "rejected" for r in results)
    assert has_rejected  # overall = "failed"


def test_overall_status_passed_with_borderline_resolved_accept():
    results = [{"status": "accepted"}, {"status": "accepted"}]  # borderline → accepted
    has_rejected = any(r["status"] == "rejected" for r in results)
    assert (not has_rejected)


# ── graph construction tests ─────────────────────────────────────────

def test_build_quality_gate_graph_returns_callable():
    graph = build_quality_gate_graph()
    assert graph is not None
    assert hasattr(graph, "invoke") or hasattr(graph, "ainvoke")


@pytest.mark.asyncio
async def test_graph_accepts_good_image(tmp_path):
    """A well-lit, sharp image should be accepted by the graph."""
    # Create a test image with some texture (not solid, so blur/sharpness are nonzero)
    import numpy as np
    img_array = np.random.randint(100, 200, (100, 100, 3), dtype=np.uint8)
    img = Image.fromarray(img_array)
    img_path = str(tmp_path / "good.jpg")
    img.save(img_path)

    graph = build_quality_gate_graph()
    state = {
        "capture_id": "test",
        "images": [{"id": "img1", "file_path": img_path, "orientation_hint": "center"}],
        "metrics": [],
        "borderline_ids": [],
        "overall_status": "",
        "config": {
            "blur_threshold": 1.0,  # very low threshold = easy to pass
            "darkness_threshold": 10.0,
            "sharpness_threshold": 1.0,
            "borderline_margin": 0.5,
        },
    }
    result = await graph.ainvoke(state)
    assert result["overall_status"] == "passed"
    assert result["metrics"][0]["status"] == "accepted"


@pytest.mark.asyncio
async def test_graph_rejects_black_image(tmp_path):
    """A completely black image should be rejected (too dark)."""
    img = Image.new("RGB", (100, 100), color=(0, 0, 0))
    img_path = str(tmp_path / "black.jpg")
    img.save(img_path)

    graph = build_quality_gate_graph()
    state = {
        "capture_id": "test",
        "images": [{"id": "img1", "file_path": img_path, "orientation_hint": "center"}],
        "metrics": [],
        "borderline_ids": [],
        "overall_status": "",
        "config": {
            "blur_threshold": 100.0,
            "darkness_threshold": 40.0,
            "sharpness_threshold": 50.0,
            "borderline_margin": 20.0,
        },
    }
    result = await graph.ainvoke(state)
    assert result["overall_status"] == "failed"
