"""Comparison Agent — LangGraph StateGraph implementation.

Graph: pair_images → normalize → structural_diff → extract_regions →
       analyze_candidates → apply_language_policy → compose_followups
"""

from __future__ import annotations

import logging
from pathlib import Path

from langgraph.graph import StateGraph, END

from app.agents.state import ComparisonState
from app.agents.comparison.tools import (
    normalize_exposure, compute_structural_diff,
    extract_candidate_regions, crop_region, save_crop,
    create_side_by_side, parse_analysis_response,
    apply_language_policy,
)
from app.agents.comparison.prompts import ANALYZE_CANDIDATE_PROMPT, COMPOSE_FOLLOWUP_PROMPT
from app.config import get_settings
from app.db import crud

from sqlalchemy.ext.asyncio import AsyncSession
from app.models.comparison import Comparison

logger = logging.getLogger(__name__)


# ── Node functions ────────────────────────────────────────

def pair_images_node(state: ComparisonState) -> dict:
    """Pair move-in and move-out images by position/sequence."""
    mi = state["move_in_images"]
    mo = state["move_out_images"]

    pairs = []
    # Match by orientation hint first, then by sequence
    mi_by_hint = {img.get("orientation_hint", ""): img for img in mi}

    for out_img in mo:
        hint = out_img.get("orientation_hint", "")
        if hint and hint in mi_by_hint:
            pairs.append({
                "move_in_path": mi_by_hint[hint]["file_path"],
                "move_out_path": out_img["file_path"],
                "orientation": hint,
                "move_in_id": mi_by_hint[hint]["id"],
                "move_out_id": out_img["id"],
            })
            del mi_by_hint[hint]

    # Fall back to sequence matching for unpaired
    unpaired_mi = sorted(mi_by_hint.values(), key=lambda x: x.get("seq", 0))
    unpaired_mo = [img for img in mo if not any(p["move_out_id"] == img["id"] for p in pairs)]
    unpaired_mo.sort(key=lambda x: x.get("seq", 0))

    for i, out_img in enumerate(unpaired_mo):
        if i < len(unpaired_mi):
            pairs.append({
                "move_in_path": unpaired_mi[i]["file_path"],
                "move_out_path": out_img["file_path"],
                "orientation": "seq_match",
                "move_in_id": unpaired_mi[i]["id"],
                "move_out_id": out_img["id"],
            })

    return {"paired_images": pairs}


def normalize_node(state: ComparisonState) -> dict:
    """Normalize exposure for each image pair (done in-place conceptually)."""
    # We'll normalize during structural_diff to avoid extra disk I/O
    return {}


def structural_diff_node(state: ComparisonState) -> dict:
    """Compute SSIM structural diff for each pair and extract regions."""
    cfg = state["config"]
    threshold = cfg.get("structural_diff_threshold", 0.15)
    max_candidates = cfg.get("max_candidates_per_room", 20)
    all_regions = []

    for pair in state["paired_images"]:
        try:
            norm1, norm2 = normalize_exposure(pair["move_in_path"], pair["move_out_path"])
            score, diff_map = compute_structural_diff(norm1, norm2)
            regions = extract_candidate_regions(diff_map, threshold)

            for region in regions:
                region["pair_orientation"] = pair["orientation"]
                region["move_in_path"] = pair["move_in_path"]
                region["move_out_path"] = pair["move_out_path"]
                region["move_in_id"] = pair["move_in_id"]
                region["move_out_id"] = pair["move_out_id"]
                region["ssim_score"] = score

            all_regions.extend(regions)
        except Exception as e:
            logger.error(f"Structural diff failed for pair {pair['orientation']}: {e}")

    # Limit to top N by area
    all_regions.sort(key=lambda r: r["area"], reverse=True)
    return {"diff_regions": all_regions[:max_candidates]}


async def analyze_candidates_node(state: ComparisonState) -> dict:
    """Use vision LLM to analyze each candidate region."""
    candidates = []
    cfg = state["config"]
    min_conf = cfg.get("min_candidate_confidence", 0.3)
    comparison_id = state["comparison_id"]

    try:
        from app.agents.llm_provider import get_llm_provider
        llm = get_llm_provider()
        has_llm = True
    except RuntimeError:
        has_llm = False
        logger.warning("No LLM configured, using CV-only confidence")

    for i, region in enumerate(state["diff_regions"]):
        # Save crops for the report
        try:
            import cv2
            img_in = cv2.imread(region["move_in_path"])
            img_out = cv2.imread(region["move_out_path"])
            if img_in is not None and img_out is not None:
                h = min(img_in.shape[0], img_out.shape[0])
                w = min(img_in.shape[1], img_out.shape[1])
                img_in = cv2.resize(img_in, (w, h))
                img_out = cv2.resize(img_out, (w, h))

                sbs = create_side_by_side(img_in, img_out, region)
                crop_path = f"data/images/comparisons/{comparison_id}/candidate_{i}.jpg"
                save_crop(sbs, crop_path)
            else:
                crop_path = ""
        except Exception as e:
            logger.error(f"Crop creation failed: {e}")
            crop_path = ""

        if has_llm:
            prompt = ANALYZE_CANDIDATE_PROMPT.format(
                room=state["room"],
                x=region["x"], y=region["y"],
                w=region["w"], h=region["h"],
            )
            try:
                # Send side-by-side crop to LLM
                if crop_path and Path(crop_path).exists():
                    response = await llm.analyze_image(crop_path, prompt)
                else:
                    response = await llm.analyze_images(
                        [region["move_in_path"], region["move_out_path"]], prompt
                    )
                analysis = parse_analysis_response(response)
            except Exception as e:
                logger.error(f"LLM analysis failed for region {i}: {e}")
                analysis = {
                    "analysis": "Automated analysis unavailable — manual review recommended",
                    "confidence": region["ssim_delta"],
                    "reason_codes": ["other"],
                    "needs_closeup": True,
                }
        else:
            analysis = {
                "analysis": "Possible change detected by structural comparison",
                "confidence": min(region["ssim_delta"] * 2, 0.9),
                "reason_codes": ["other"],
                "needs_closeup": True,
            }

        if analysis["confidence"] >= min_conf:
            candidates.append({
                "region": {"x": region["x"], "y": region["y"], "w": region["w"], "h": region["h"]},
                "confidence": analysis["confidence"],
                "reason_codes": analysis["reason_codes"],
                "analysis": analysis["analysis"],
                "needs_closeup": analysis.get("needs_closeup", False),
                "crop_path": crop_path,
                "move_in_id": region["move_in_id"],
                "move_out_id": region["move_out_id"],
            })

    return {"candidates": candidates}


def language_policy_node(state: ComparisonState) -> dict:
    """Scrub forbidden terms from all candidate analyses."""
    settings = get_settings()
    forbidden = settings.language_policy.forbidden
    hedging = settings.language_policy.required_hedging

    cleaned = []
    for cand in state["candidates"]:
        cand_copy = dict(cand)
        cand_copy["analysis"] = apply_language_policy(cand["analysis"], forbidden, hedging)
        cleaned.append(cand_copy)

    return {"candidates": cleaned}


async def compose_followups_node(state: ComparisonState) -> dict:
    """Generate follow-up messages for candidates."""
    followups = []

    try:
        from app.agents.llm_provider import get_llm_provider
        llm = get_llm_provider()
        has_llm = True
    except RuntimeError:
        has_llm = False

    settings = get_settings()

    for cand in state["candidates"]:
        if has_llm:
            prompt = COMPOSE_FOLLOWUP_PROMPT.format(
                room=state["room"],
                analysis=cand["analysis"],
                confidence=cand["confidence"],
                reason_codes=", ".join(cand.get("reason_codes", [])),
            )
            try:
                message = await llm.chat(prompt)
                message = apply_language_policy(
                    message, settings.language_policy.forbidden,
                    settings.language_policy.required_hedging,
                )
            except Exception:
                message = _default_followup(cand)
        else:
            message = _default_followup(cand)

        followups.append({
            "candidate_index": len(followups),
            "message": message,
            "needs_closeup": cand.get("needs_closeup", False),
        })

    return {"followups": followups}


def _default_followup(cand: dict) -> str:
    """Generate a default follow-up message without LLM."""
    return (
        f"A candidate difference was identified in this area. "
        f"The analysis indicates: {cand['analysis'][:150]}. "
        f"Could you please confirm or provide additional context about this area?"
    )


# ── Build graph ───────────────────────────────────────────

def build_comparison_graph() -> StateGraph:
    graph = StateGraph(ComparisonState)

    graph.add_node("pair_images", pair_images_node)
    graph.add_node("normalize", normalize_node)
    graph.add_node("structural_diff", structural_diff_node)
    graph.add_node("analyze_candidates", analyze_candidates_node)
    graph.add_node("language_policy", language_policy_node)
    graph.add_node("compose_followups", compose_followups_node)

    graph.set_entry_point("pair_images")
    graph.add_edge("pair_images", "normalize")
    graph.add_edge("normalize", "structural_diff")
    graph.add_edge("structural_diff", "analyze_candidates")
    graph.add_edge("analyze_candidates", "language_policy")
    graph.add_edge("language_policy", "compose_followups")
    graph.add_edge("compose_followups", END)

    return graph.compile()


# ── Public API ────────────────────────────────────────────

async def run_comparison(comparison: Comparison, db: AsyncSession) -> dict:
    """Run the comparison agent on a move-in/move-out pair."""
    settings = get_settings()

    # Load captures and their images
    mi_capture = await crud.get_capture(db, comparison.move_in_capture_id)
    mo_capture = await crud.get_capture(db, comparison.move_out_capture_id)

    if not mi_capture or not mo_capture:
        return {"status": "error", "message": "Missing captures"}

    mi_images = [{"id": img.id, "file_path": img.file_path,
                   "orientation_hint": img.orientation_hint, "seq": img.seq}
                  for img in mi_capture.images]
    mo_images = [{"id": img.id, "file_path": img.file_path,
                   "orientation_hint": img.orientation_hint, "seq": img.seq}
                  for img in mo_capture.images]

    initial_state: ComparisonState = {
        "comparison_id": comparison.id,
        "room": comparison.room,
        "move_in_images": mi_images,
        "move_out_images": mo_images,
        "paired_images": [],
        "diff_regions": [],
        "candidates": [],
        "followups": [],
        "config": {
            "structural_diff_threshold": settings.comparison.structural_diff_threshold,
            "min_candidate_confidence": settings.comparison.min_candidate_confidence,
            "max_candidates_per_room": settings.comparison.max_candidates_per_room,
        },
    }

    graph = build_comparison_graph()
    result = await graph.ainvoke(initial_state)

    # Save candidates to DB
    for i, cand in enumerate(result["candidates"]):
        followup = result["followups"][i] if i < len(result["followups"]) else {}
        await crud.create_candidate(
            db,
            comparison_id=comparison.id,
            region_json=cand.get("region"),
            confidence=cand.get("confidence", 0.0),
            reason_codes=cand.get("reason_codes"),
            crop_path=cand.get("crop_path", ""),
        )

    return {
        "status": "complete",
        "pairs_analyzed": len(result["paired_images"]),
        "regions_found": len(result["diff_regions"]),
        "candidates": len(result["candidates"]),
        "followups": result["followups"],
    }
