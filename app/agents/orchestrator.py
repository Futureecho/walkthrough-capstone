"""Agent orchestrator: wires quality gate -> coverage review -> comparison."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud
from app.services.ws_manager import ws_manager

logger = logging.getLogger(__name__)


async def _get_llm_provider(db: AsyncSession) -> str:
    """Get the llm_provider from the tenant DB's company_settings."""
    settings = await crud.get_company_settings(db)
    if not settings:
        return "openai"
    return settings.llm_provider


async def _set_review_flag(session_id: str, flag: str, db: AsyncSession):
    """Set session.review_flag — last write wins for multi-capture sessions."""
    session = await crud.get_session(db, session_id)
    if session:
        session.review_flag = flag
        await db.commit()


async def run_capture_pipeline(
    capture_id: str,
    session_id: str,
    db: AsyncSession,
    company_id: str = "",
):
    """Run quality gate then coverage review for a submitted capture."""
    from app.agents.quality_gate.graph import run_quality_gate
    from app.agents.coverage_review.graph import run_coverage_review

    capture = await crud.get_capture(db, capture_id)
    if not capture:
        return

    # Check if company has opted for manual review
    llm_provider = await _get_llm_provider(db)
    if llm_provider == "none":
        await crud.update_capture(db, capture, status="passed")
        await _set_review_flag(session_id, "manual_review", db)
        await ws_manager.broadcast(session_id, {
            "event": "pipeline_skipped",
            "capture_id": capture_id,
            "data": {"reason": "manual_review"},
        })
        return

    try:
        # Step 1: Quality Gate
        quality_result = await run_quality_gate(capture, db)
        await ws_manager.broadcast(session_id, {
            "event": "quality_update",
            "capture_id": capture_id,
            "data": quality_result,
        })

        # If quality gate failed, stop (no review flag — tenant retries)
        if quality_result.get("status") == "failed":
            await crud.update_capture(db, capture, status="failed", metrics_json=quality_result)
            return

        # Step 2: Coverage Review
        coverage_result = await run_coverage_review(capture, db)
        await ws_manager.broadcast(session_id, {
            "event": "coverage_update",
            "capture_id": capture_id,
            "data": coverage_result,
        })

        # All required guided positions captured → pass regardless of LLM coverage pct
        required_hints = {"center-from-door", "center-opposite-wall",
                          "corner-left-near", "corner-right-near",
                          "corner-left-far", "corner-right-far", "ceiling"}
        captured_hints = {img.orientation_hint for img in capture.images if img.orientation_hint}
        all_required = required_hints.issubset(captured_hints)

        final_status = "passed" if (coverage_result.get("complete", False) or all_required) else "needs_coverage"
        await crud.update_capture(
            db, capture,
            status=final_status,
            metrics_json=quality_result,
            coverage_json=coverage_result,
        )

        # AI succeeded — mark session as AI-reviewed
        await _set_review_flag(session_id, "ai_review_complete", db)

        # Step 3: Auto-trigger comparison if this is a move-out and matching move-in exists
        if final_status == "passed":
            await _try_auto_comparison(capture, session_id, db)

    except Exception:
        # AI pipeline failed — degrade to manual review
        await _set_review_flag(session_id, "manual_review", db)
        raise


async def _try_auto_comparison(capture, session_id: str, db: AsyncSession):
    """If this is a move-out capture and a matching move-in exists, auto-create comparison."""
    session = await crud.get_session(db, capture.session_id)
    if not session or session.type != "move_out":
        return

    all_sessions = await crud.list_sessions_for_property(db, session.property_id)
    move_in_sessions = [s for s in all_sessions if s.type == "move_in"]
    if not move_in_sessions:
        return

    for mi_session in move_in_sessions:
        mi_captures = await crud.list_captures_for_session(db, mi_session.id)
        for mi_cap in mi_captures:
            if mi_cap.room == capture.room and mi_cap.status == "passed":
                comp = await crud.create_comparison(
                    db, capture.room, mi_cap.id, capture.id
                )
                await run_comparison_pipeline(comp.id, session_id, db)
                return


async def run_comparison_pipeline(comparison_id: str, session_id: str, db: AsyncSession):
    """Run comparison agent for a move-in/move-out pair."""
    from app.agents.comparison.graph import run_comparison

    comparison = await crud.get_comparison(db, comparison_id)
    if not comparison:
        return

    await crud.update_comparison(db, comparison, status="processing")

    result = await run_comparison(comparison, db)

    await crud.update_comparison(
        db, comparison,
        status="complete",
        diff_data_json=result,
    )

    await ws_manager.broadcast(session_id, {
        "event": "comparison_update",
        "comparison_id": comparison_id,
        "data": result,
    })
