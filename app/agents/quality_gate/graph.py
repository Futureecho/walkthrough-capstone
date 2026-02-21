"""Quality Gate Agent — LangGraph StateGraph implementation.

Graph: compute_metrics → evaluate → (accept | redo | borderline→LLM judge)
Uses classical CV first, only calls LLM for borderline cases.
"""

from __future__ import annotations

import logging
from typing import Literal

from langgraph.graph import StateGraph, END

from app.agents.state import QualityGateState, ImageMetrics
from app.agents.quality_gate.tools import (
    compute_blur, compute_darkness, compute_sharpness, decide_quality, explain_quality,
)
from app.agents.quality_gate.prompts import BORDERLINE_JUDGE_PROMPT
from app.config import get_settings
from app.db import crud

from sqlalchemy.ext.asyncio import AsyncSession
from app.models.capture import Capture

logger = logging.getLogger(__name__)


# ── Node functions ────────────────────────────────────────

def compute_metrics_node(state: QualityGateState) -> dict:
    """Compute CV quality metrics for all images."""
    metrics = []
    for img in state["images"]:
        fp = img["file_path"]
        try:
            blur = compute_blur(fp)
            darkness = compute_darkness(fp)
            sharpness = compute_sharpness(fp)
        except Exception as e:
            logger.error(f"CV metrics failed for {fp}: {e}")
            blur, darkness, sharpness = 0.0, 0.0, 0.0

        metrics.append(ImageMetrics(
            image_id=img["id"],
            file_path=fp,
            blur_score=blur,
            darkness_score=darkness,
            sharpness_score=sharpness,
            status="pending",
            llm_verdict="",
        ))
    return {"metrics": metrics}


def evaluate_node(state: QualityGateState) -> dict:
    """Apply deterministic thresholds to classify each image."""
    cfg = state["config"]
    borderline_ids = []
    updated_metrics = []

    for m in state["metrics"]:
        verdict = decide_quality(
            m["blur_score"], m["darkness_score"], m["sharpness_score"],
            cfg["blur_threshold"], cfg["darkness_threshold"],
            cfg["sharpness_threshold"], cfg["borderline_margin"],
        )
        updated = {**m, "status": verdict}
        updated_metrics.append(updated)
        if verdict == "borderline":
            borderline_ids.append(m["image_id"])

    return {"metrics": updated_metrics, "borderline_ids": borderline_ids}


def should_llm_judge(state: QualityGateState) -> Literal["llm_judge", "finalize"]:
    """Conditional edge: go to LLM judge if there are borderline images."""
    if state["borderline_ids"]:
        return "llm_judge"
    return "finalize"


async def llm_judge_node(state: QualityGateState) -> dict:
    """Use vision LLM to judge borderline images."""
    try:
        from app.agents.llm_provider import get_llm_provider
        llm = get_llm_provider()
    except RuntimeError:
        # No LLM configured — accept borderline images
        logger.warning("No LLM configured, accepting borderline images")
        updated = []
        for m in state["metrics"]:
            if m["image_id"] in state["borderline_ids"]:
                updated.append({**m, "status": "accepted", "llm_verdict": "accepted_no_llm"})
            else:
                updated.append(m)
        return {"metrics": updated, "borderline_ids": []}

    cfg = state["config"]
    updated = []
    for m in state["metrics"]:
        if m["image_id"] in state["borderline_ids"]:
            prompt = BORDERLINE_JUDGE_PROMPT.format(
                blur_score=m["blur_score"],
                darkness_score=m["darkness_score"],
                sharpness_score=m["sharpness_score"],
                blur_threshold=cfg["blur_threshold"],
                darkness_threshold=cfg["darkness_threshold"],
                sharpness_threshold=cfg["sharpness_threshold"],
            )
            try:
                response = await llm.analyze_image(m["file_path"], prompt)
                verdict = "accepted" if "ACCEPT" in response.upper() else "rejected"
            except Exception as e:
                logger.error(f"LLM judge failed for {m['image_id']}: {e}")
                verdict = "accepted"  # fail-open for borderline
            updated.append({**m, "status": verdict, "llm_verdict": verdict})
        else:
            updated.append(m)
    return {"metrics": updated, "borderline_ids": []}


def finalize_node(state: QualityGateState) -> dict:
    """Determine overall pass/fail status."""
    any_rejected = any(m["status"] == "rejected" for m in state["metrics"])
    return {"overall_status": "failed" if any_rejected else "passed"}


# ── Build graph ───────────────────────────────────────────

def build_quality_gate_graph() -> StateGraph:
    graph = StateGraph(QualityGateState)

    graph.add_node("compute_metrics", compute_metrics_node)
    graph.add_node("evaluate", evaluate_node)
    graph.add_node("llm_judge", llm_judge_node)
    graph.add_node("finalize", finalize_node)

    graph.set_entry_point("compute_metrics")
    graph.add_edge("compute_metrics", "evaluate")
    graph.add_conditional_edges("evaluate", should_llm_judge, {
        "llm_judge": "llm_judge",
        "finalize": "finalize",
    })
    graph.add_edge("llm_judge", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile()


# ── Public API ────────────────────────────────────────────

async def run_quality_gate(capture: Capture, db: AsyncSession) -> dict:
    """Run the quality gate agent on a capture's images."""
    settings = get_settings()
    cfg = {
        "blur_threshold": settings.quality_gate.blur_threshold,
        "darkness_threshold": settings.quality_gate.darkness_threshold,
        "sharpness_threshold": settings.quality_gate.sharpness_threshold,
        "borderline_margin": settings.quality_gate.borderline_margin,
    }

    images = [{"id": img.id, "file_path": img.file_path, "orientation_hint": img.orientation_hint}
              for img in capture.images]

    initial_state: QualityGateState = {
        "capture_id": capture.id,
        "images": images,
        "metrics": [],
        "borderline_ids": [],
        "overall_status": "",
        "config": cfg,
    }

    graph = build_quality_gate_graph()
    result = await graph.ainvoke(initial_state)

    # Update individual image quality_json in DB
    for m in result["metrics"]:
        img = await crud.get_capture_image(db, m["image_id"])
        if img:
            await crud.update_capture_image(db, img, quality_json={
                "blur_score": m["blur_score"],
                "darkness_score": m["darkness_score"],
                "sharpness_score": m["sharpness_score"],
                "status": m["status"],
                "llm_verdict": m["llm_verdict"],
            })

    # Build per-image results with rejection reasons
    images_out = {}
    for m in result["metrics"]:
        entry = {
            "status": m["status"],
            "blur_score": m["blur_score"],
            "darkness_score": m["darkness_score"],
            "sharpness_score": m["sharpness_score"],
        }
        if m["status"] == "rejected":
            entry["reasons"] = explain_quality(
                m["blur_score"], m["darkness_score"], m["sharpness_score"],
                cfg["blur_threshold"], cfg["darkness_threshold"], cfg["sharpness_threshold"],
            )
        images_out[m["image_id"]] = entry

    return {"status": result["overall_status"], "images": images_out}
