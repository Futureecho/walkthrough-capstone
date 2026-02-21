"""Coverage Review Agent — LangGraph StateGraph implementation.

Graph: summarize_all → aggregate → decide_completeness → (complete | generate_instructions)
"""

from __future__ import annotations

import logging
from typing import Literal

from langgraph.graph import StateGraph, END

from app.agents.state import CoverageState
from app.agents.coverage_review.tools import (
    aggregate_coverage, parse_summary_response, parse_instructions_response,
)
from app.agents.coverage_review.prompts import SUMMARIZE_VIEW_PROMPT, NEXT_SHOTS_PROMPT
from app.config import get_settings
from app.db import crud

from sqlalchemy.ext.asyncio import AsyncSession
from app.models.capture import Capture

logger = logging.getLogger(__name__)


# ── Node functions ────────────────────────────────────────

async def summarize_all_node(state: CoverageState) -> dict:
    """Use vision LLM to summarize what's visible in each image."""
    try:
        from app.agents.llm_provider import get_llm_provider
        llm = get_llm_provider()
    except RuntimeError:
        # No LLM — generate basic summaries from orientation hints
        logger.warning("No LLM configured, using orientation-based summaries")
        summaries = []
        for img in state["images"]:
            hint = img.get("orientation_hint", "")
            areas = _hint_to_areas(hint)
            summaries.append({
                "image_id": img["id"],
                "visible_surfaces": [],
                "fixtures": [],
                "coverage_areas": areas,
                "quality_notes": f"Auto-generated from orientation: {hint}",
            })
        return {"summaries": summaries}

    room = state["room"]
    summaries = []

    for img in state["images"]:
        prompt = SUMMARIZE_VIEW_PROMPT.format(
            room_type=room,
            orientation_hint=img.get("orientation_hint", "unknown"),
        )
        try:
            response = await llm.analyze_image(img["file_path"], prompt)
            parsed = parse_summary_response(response)
            parsed["image_id"] = img["id"]
            summaries.append(parsed)
        except Exception as e:
            logger.error(f"Vision summarize failed for {img['id']}: {e}")
            hint = img.get("orientation_hint", "")
            summaries.append({
                "image_id": img["id"],
                "visible_surfaces": [],
                "fixtures": [],
                "coverage_areas": _hint_to_areas(hint),
                "quality_notes": f"LLM error: {str(e)[:100]}",
            })

    return {"summaries": summaries}


def aggregate_node(state: CoverageState) -> dict:
    """Deterministic aggregation against room checklist."""
    result = aggregate_coverage(state["summaries"], state["room"])
    return {"coverage": result}


def decide_completeness(state: CoverageState) -> Literal["complete", "generate_instructions"]:
    """Check if coverage meets threshold."""
    cfg = state["config"]
    pct = state["coverage"].get("coverage_pct", 0)
    if pct >= cfg.get("min_coverage_pct", 80.0):
        return "complete"
    return "generate_instructions"


def complete_node(state: CoverageState) -> dict:
    """Mark coverage as complete."""
    return {"complete": True, "instructions": []}


async def generate_instructions_node(state: CoverageState) -> dict:
    """Generate next-best-shot instructions for missing areas."""
    coverage = state["coverage"]
    missing = coverage.get("missing", [])

    # Always provide basic deterministic instructions
    basic_instructions = [
        f"Take a photo showing the {area} area" for area in missing[:3]
    ]

    try:
        from app.agents.llm_provider import get_llm_provider
        llm = get_llm_provider()
        prompt = NEXT_SHOTS_PROMPT.format(
            room_type=state["room"],
            covered=", ".join(coverage.get("covered", [])),
            missing=", ".join(missing),
            coverage_pct=coverage.get("coverage_pct", 0),
        )
        response = await llm.chat(prompt)
        instructions = parse_instructions_response(response)
        if instructions:
            return {"complete": False, "instructions": instructions}
    except Exception as e:
        logger.warning(f"LLM instructions failed, using basic: {e}")

    return {"complete": False, "instructions": basic_instructions}


# ── Helpers ───────────────────────────────────────────────

def _hint_to_areas(hint: str) -> list[str]:
    """Map orientation hint to likely coverage areas."""
    mapping = {
        "center-from-door": ["wall-far", "floor", "door"],
        "center-opposite-wall": ["wall-near", "door", "floor"],
        "corner-left-near": ["wall-left", "wall-near", "corner-left-near"],
        "corner-right-near": ["wall-right", "wall-near", "corner-right-near"],
        "corner-left-far": ["wall-left", "wall-far", "corner-left-far"],
        "corner-right-far": ["wall-right", "wall-far", "corner-right-far"],
        "ceiling": ["ceiling"],
        "floor": ["floor"],
    }
    return mapping.get(hint, [])


# ── Build graph ───────────────────────────────────────────

def build_coverage_graph() -> StateGraph:
    graph = StateGraph(CoverageState)

    graph.add_node("summarize_all", summarize_all_node)
    graph.add_node("aggregate", aggregate_node)
    graph.add_node("complete", complete_node)
    graph.add_node("generate_instructions", generate_instructions_node)

    graph.set_entry_point("summarize_all")
    graph.add_edge("summarize_all", "aggregate")
    graph.add_conditional_edges("aggregate", decide_completeness, {
        "complete": "complete",
        "generate_instructions": "generate_instructions",
    })
    graph.add_edge("complete", END)
    graph.add_edge("generate_instructions", END)

    return graph.compile()


# ── Public API ────────────────────────────────────────────

async def run_coverage_review(capture: Capture, db: AsyncSession) -> dict:
    """Run the coverage review agent on a capture's images."""
    settings = get_settings()

    images = [{"id": img.id, "file_path": img.file_path, "orientation_hint": img.orientation_hint}
              for img in capture.images]

    initial_state: CoverageState = {
        "capture_id": capture.id,
        "room": capture.room,
        "images": images,
        "summaries": [],
        "coverage": {},
        "complete": False,
        "instructions": [],
        "config": {
            "min_coverage_pct": settings.coverage.min_coverage_pct,
        },
    }

    graph = build_coverage_graph()
    result = await graph.ainvoke(initial_state)

    return {
        "coverage_pct": result["coverage"].get("coverage_pct", 0),
        "complete": result["complete"],
        "covered_areas": result["coverage"].get("covered", []),
        "missing_areas": result["coverage"].get("missing", []),
        "instructions": result["instructions"],
    }
