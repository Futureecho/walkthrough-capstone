"""Data export: full company ZIP, per-property ZIP, PDF report."""

from __future__ import annotations

import io
import shutil
import tempfile
from pathlib import Path
from zipfile import ZipFile

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud


async def export_full_zip(company_id: str, db: AsyncSession) -> bytes:
    """Export entire company data: tenant.db + all images -> ZIP."""
    buf = io.BytesIO()
    tenant_db_path = Path(f"data/companies/{company_id}/tenant.db")
    images_dir = Path(f"data/companies/{company_id}/images")

    with ZipFile(buf, "w") as zf:
        # Include the database
        if tenant_db_path.exists():
            zf.write(str(tenant_db_path), "tenant.db")

        # Include all images
        if images_dir.exists():
            for img_file in images_dir.rglob("*"):
                if img_file.is_file():
                    arcname = f"images/{img_file.relative_to(images_dir)}"
                    zf.write(str(img_file), arcname)

    return buf.getvalue()


async def export_property_zip(company_id: str, property_id: str, db: AsyncSession) -> bytes:
    """Export a single property's sessions, captures, and images -> ZIP."""
    buf = io.BytesIO()
    images_dir = Path(f"data/companies/{company_id}/images")

    prop = await crud.get_property(db, property_id)
    if not prop:
        raise ValueError("Property not found")

    sessions = await crud.list_sessions_for_property(db, property_id)

    with ZipFile(buf, "w") as zf:
        # Write property metadata
        import json
        prop_meta = {
            "id": prop.id,
            "label": prop.label,
            "address": prop.address,
            "rooms": prop.rooms,
            "created_at": prop.created_at.isoformat(),
        }
        zf.writestr("property.json", json.dumps(prop_meta, indent=2))

        # Write sessions and their captures' images
        for session in sessions:
            session_meta = {
                "id": session.id,
                "type": session.type,
                "tenant_name": session.tenant_name,
                "report_status": session.report_status,
                "created_at": session.created_at.isoformat(),
            }
            zf.writestr(f"sessions/{session.id}/session.json", json.dumps(session_meta, indent=2))

            captures = await crud.list_captures_for_session(db, session.id)
            for cap in captures:
                cap_images_dir = images_dir / cap.id
                if cap_images_dir.exists():
                    for img_file in cap_images_dir.rglob("*"):
                        if img_file.is_file():
                            arcname = f"sessions/{session.id}/{cap.room}/{img_file.relative_to(cap_images_dir)}"
                            zf.write(str(img_file), arcname)

    return buf.getvalue()


async def export_pdf(session_id: str, db: AsyncSession) -> bytes:
    """Export a session as PDF report."""
    from app.services.pdf_generator import generate_pdf
    return await generate_pdf(db, session_id)
