"""PDF generation service using xhtml2pdf."""

from __future__ import annotations

import base64
import io
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def _encode_image_file(path: str) -> str:
    """Read an image file and return base64-encoded string."""
    full_path = Path(path)
    if not full_path.exists():
        return ""
    data = full_path.read_bytes()
    return base64.standard_b64encode(data).decode("utf-8")


async def generate_pdf(db: AsyncSession, session_id: str) -> bytes:
    """Generate a PDF report for a session. Returns PDF bytes."""
    from xhtml2pdf import pisa

    session = await crud.get_session(db, session_id)
    if not session:
        raise ValueError("Session not found")

    prop = await crud.get_property(db, session.property_id)

    # Gather room data
    captures = await crud.list_captures_for_session(db, session_id)
    comparisons = await crud.list_comparisons_for_property(db, session.property_id)

    # Build comparison lookup by room
    comp_by_room = {}
    for comp in comparisons:
        comp_by_room[comp.room] = comp

    rooms = {}
    total_flagged = 0
    total_accepted = 0
    total_cost = 0.0

    for capture in captures:
        comp = comp_by_room.get(capture.room)
        candidates = []
        if comp and comp.candidates:
            for cand in comp.candidates:
                total_flagged += 1
                cand_data = {
                    "confidence": cand.confidence,
                    "reason_codes": cand.reason_codes or [],
                    "tenant_response": cand.tenant_response,
                    "tenant_comment": cand.tenant_comment,
                    "owner_accepted": cand.owner_accepted,
                    "repair_cost": cand.repair_cost or 0,
                    "owner_notes": cand.owner_notes or "",
                    "crop_b64": _encode_image_file(cand.crop_path) if cand.crop_path else "",
                    "ref_b64": "",  # Could add reference image pairing
                }
                if cand.owner_accepted:
                    total_accepted += 1
                    total_cost += cand.repair_cost or 0
                candidates.append(cand_data)

        rooms[capture.room] = {
            "status": capture.status,
            "candidates": candidates,
        }

    # Render Jinja2 template
    env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)))
    template = env.get_template("pdf_report.html.j2")
    html = template.render(
        property=prop,
        session=session,
        rooms=rooms,
        total_flagged=total_flagged,
        total_accepted=total_accepted,
        total_cost=total_cost,
        report_date=datetime.now(timezone.utc).strftime("%B %d, %Y"),
    )

    # Convert HTML → PDF
    pdf_buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.StringIO(html), dest=pdf_buffer)
    if pisa_status.err:
        raise RuntimeError(f"PDF generation failed with {pisa_status.err} errors")

    return pdf_buffer.getvalue()


async def generate_work_order_pdf(db: AsyncSession, work_order_id: str) -> bytes:
    """Generate a work order PDF. Returns PDF bytes."""
    from xhtml2pdf import pisa
    from app.models import WorkOrder, Technician, Concern

    wo = await crud.get_work_order(db, work_order_id)
    if not wo:
        raise ValueError("Work order not found")

    tech = await crud.get_technician(db, wo.technician_id)
    session = await crud.get_session(db, wo.session_id)
    prop = await crud.get_property(db, session.property_id) if session else None

    # Load included concerns with base64 thumbnails
    concerns = []
    for cid in (wo.included_concern_ids or []):
        concern = await crud.get_concern(db, cid)
        if concern:
            thumb_b64 = ""
            if concern.thumbnail_path:
                try:
                    from app.services.image_store import read_image_sync
                    img_data = read_image_sync(concern.thumbnail_path)
                    thumb_b64 = base64.standard_b64encode(img_data).decode("utf-8")
                except Exception:
                    pass
            concerns.append({
                "title": concern.title,
                "description": concern.description,
                "room": concern.room,
                "thumb_b64": thumb_b64,
            })

    # Order type labels
    type_labels = {
        "nte": "Not to Exceed",
        "call_estimate": "Call with Estimate",
        "proceed": "Proceed with Work",
    }

    env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)))
    template = env.get_template("work_order.html.j2")
    html = template.render(
        work_order=wo,
        technician=tech,
        session=session,
        property=prop,
        concerns=concerns,
        order_type_label=type_labels.get(wo.order_type, wo.order_type),
        report_date=datetime.now(timezone.utc).strftime("%B %d, %Y"),
    )

    pdf_buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.StringIO(html), dest=pdf_buffer)
    if pisa_status.err:
        raise RuntimeError(f"Work order PDF generation failed with {pisa_status.err} errors")

    return pdf_buffer.getvalue()
