"""Work order API — create, update, generate PDF, dispatch."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud
from app.dependencies import require_auth, get_company_db

router = APIRouter(prefix="/api/owner/work-orders", tags=["work_orders"])


@router.post("", status_code=201)
async def create_work_order(
    body: dict,
    auth=Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    session_id = body.get("session_id")
    technician_id = body.get("technician_id")
    order_type = body.get("order_type")

    if not session_id or not technician_id or not order_type:
        raise HTTPException(400, "session_id, technician_id, and order_type are required")

    session = await crud.get_session(db, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    tech = await crud.get_technician(db, technician_id)
    if not tech:
        raise HTTPException(404, "Technician not found")

    wo = await crud.create_work_order(
        db,
        session_id=session_id,
        technician_id=technician_id,
        contact_name=body.get("contact_name", ""),
        contact_phone=body.get("contact_phone", ""),
        order_type=order_type,
        nte_amount=body.get("nte_amount"),
        included_concern_ids=body.get("included_concern_ids", []),
    )

    return {
        "id": wo.id,
        "session_id": wo.session_id,
        "technician_id": wo.technician_id,
        "order_type": wo.order_type,
        "status": wo.status,
    }


@router.get("/{wo_id}")
async def get_work_order(
    wo_id: str,
    auth=Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    wo = await crud.get_work_order(db, wo_id)
    if not wo:
        raise HTTPException(404, "Work order not found")

    tech = await crud.get_technician(db, wo.technician_id)

    # Load included concerns
    concerns = []
    for cid in (wo.included_concern_ids or []):
        c = await crud.get_concern(db, cid)
        if c:
            concerns.append({
                "id": c.id,
                "title": c.title,
                "description": c.description,
                "room": c.room,
                "thumbnail_path": c.thumbnail_path,
            })

    return {
        "id": wo.id,
        "session_id": wo.session_id,
        "technician_id": wo.technician_id,
        "technician": {"id": tech.id, "name": tech.name, "email": tech.email, "phone": tech.phone} if tech else None,
        "contact_name": wo.contact_name,
        "contact_phone": wo.contact_phone,
        "order_type": wo.order_type,
        "nte_amount": wo.nte_amount,
        "status": wo.status,
        "included_concern_ids": wo.included_concern_ids,
        "concerns": concerns,
        "dispatched_at": wo.dispatched_at.isoformat() if wo.dispatched_at else None,
        "created_at": wo.created_at.isoformat(),
    }


@router.put("/{wo_id}")
async def update_work_order(
    wo_id: str,
    body: dict,
    auth=Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    wo = await crud.get_work_order(db, wo_id)
    if not wo:
        raise HTTPException(404, "Work order not found")

    updates = {}
    for field in ("technician_id", "contact_name", "contact_phone", "order_type", "nte_amount", "included_concern_ids"):
        if field in body:
            updates[field] = body[field]

    if updates:
        wo = await crud.update_work_order(db, wo, **updates)

    return {"ok": True, "id": wo.id, "status": wo.status}


@router.post("/{wo_id}/pdf")
async def generate_work_order_pdf(
    wo_id: str,
    auth=Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    wo = await crud.get_work_order(db, wo_id)
    if not wo:
        raise HTTPException(404, "Work order not found")

    from app.services.pdf_generator import generate_work_order_pdf as gen_pdf
    pdf_bytes = await gen_pdf(db, wo_id)

    filename = f"work_order_{wo_id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/{wo_id}/dispatch")
async def dispatch_work_order(
    wo_id: str,
    auth=Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    wo = await crud.get_work_order(db, wo_id)
    if not wo:
        raise HTTPException(404, "Work order not found")

    if wo.status == "dispatched":
        raise HTTPException(400, "Work order already dispatched")

    # Check approval email is set
    settings = await crud.get_company_settings(db)
    if not settings or not settings.approval_email:
        raise HTTPException(400, "Approval email not configured. Set it in Settings.")

    tech = await crud.get_technician(db, wo.technician_id)
    if not tech:
        raise HTTPException(404, "Technician not found")

    # Generate PDF
    from app.services.pdf_generator import generate_work_order_pdf as gen_pdf
    pdf_bytes = await gen_pdf(db, wo_id)

    # Load session + property for email subject
    session = await crud.get_session(db, wo.session_id)
    prop = await crud.get_property(db, session.property_id) if session else None
    property_label = prop.label if prop else "Property"

    # Send email
    from app.services.email import send_work_order_email
    subject = f"Work Order — {property_label}"
    filename = f"work_order_{wo_id[:8]}.pdf"

    html = f"""
    <h2>Work Order Dispatch</h2>
    <p>A work order has been dispatched for <strong>{property_label}</strong>.</p>
    <p>Please find the work order PDF attached.</p>
    <p style="color:#888;font-size:12px;">Sent via Walkthru-X</p>
    """

    success = send_work_order_email(
        to=tech.email,
        cc=settings.approval_email,
        subject=subject,
        html=html,
        pdf_bytes=pdf_bytes,
        filename=filename,
    )

    if not success:
        raise HTTPException(500, "Failed to send email. Check Resend API key.")

    # Mark dispatched
    wo = await crud.update_work_order(
        db, wo,
        status="dispatched",
        dispatched_at=datetime.now(timezone.utc),
    )

    return {"ok": True, "id": wo.id, "status": "dispatched"}
