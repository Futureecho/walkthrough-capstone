"""CRUD operations for all models."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Property, Session, Capture, CaptureImage,
    Annotation, Comparison, Candidate,
)


# ── Reference Images (ghost overlay) ────────────────────

async def get_reference_images(
    db: AsyncSession, property_id: str, room: str
) -> list[CaptureImage]:
    """Return move-in capture images for a property+room (most recent session)."""
    result = await db.execute(
        select(CaptureImage)
        .join(Capture, CaptureImage.capture_id == Capture.id)
        .join(Session, Capture.session_id == Session.id)
        .where(
            Session.property_id == property_id,
            Session.type == "move_in",
            Capture.room == room,
        )
        .order_by(Session.created_at.desc(), CaptureImage.seq)
    )
    images = list(result.scalars().all())
    if not images:
        return []
    # Only return images from the most recent move-in session
    first_capture_id = images[0].capture_id
    return [img for img in images if img.capture_id == first_capture_id]


# ── Property ──────────────────────────────────────────────

async def create_property(db: AsyncSession, label: str, rooms: list[str]) -> Property:
    prop = Property(label=label, rooms=rooms)
    db.add(prop)
    await db.commit()
    await db.refresh(prop)
    return prop


async def get_property(db: AsyncSession, property_id: str) -> Property | None:
    return await db.get(Property, property_id)


async def list_properties(db: AsyncSession) -> list[Property]:
    result = await db.execute(select(Property).order_by(Property.created_at.desc()))
    return list(result.scalars().all())


# ── Session ───────────────────────────────────────────────

async def create_session(
    db: AsyncSession, property_id: str, session_type: str, tenant_name: str = ""
) -> Session:
    sess = Session(property_id=property_id, type=session_type, tenant_name=tenant_name)
    db.add(sess)
    await db.commit()
    await db.refresh(sess)
    return sess


async def get_session(db: AsyncSession, session_id: str) -> Session | None:
    return await db.get(Session, session_id)


async def list_sessions_for_property(db: AsyncSession, property_id: str) -> list[Session]:
    result = await db.execute(
        select(Session).where(Session.property_id == property_id).order_by(Session.created_at.desc())
    )
    return list(result.scalars().all())


# ── Capture ───────────────────────────────────────────────

async def create_capture(
    db: AsyncSession, session_id: str, room: str, device_meta: dict | None = None
) -> Capture:
    cap = Capture(session_id=session_id, room=room, device_meta=device_meta)
    db.add(cap)
    await db.commit()
    await db.refresh(cap)
    return cap


async def get_capture(db: AsyncSession, capture_id: str) -> Capture | None:
    return await db.get(Capture, capture_id)


async def update_capture(db: AsyncSession, capture: Capture, **kwargs) -> Capture:
    for k, v in kwargs.items():
        setattr(capture, k, v)
    await db.commit()
    await db.refresh(capture)
    return capture


async def list_captures_for_session(db: AsyncSession, session_id: str) -> list[Capture]:
    result = await db.execute(
        select(Capture).where(Capture.session_id == session_id).order_by(Capture.created_at)
    )
    return list(result.scalars().all())


# ── CaptureImage ──────────────────────────────────────────

async def create_capture_image(
    db: AsyncSession,
    capture_id: str,
    seq: int,
    file_path: str,
    thumbnail_path: str = "",
    orientation_hint: str = "",
) -> CaptureImage:
    img = CaptureImage(
        capture_id=capture_id, seq=seq, file_path=file_path,
        thumbnail_path=thumbnail_path, orientation_hint=orientation_hint,
    )
    db.add(img)
    await db.commit()
    await db.refresh(img)
    return img


async def get_capture_image(db: AsyncSession, image_id: str) -> CaptureImage | None:
    return await db.get(CaptureImage, image_id)


async def delete_capture_image(db: AsyncSession, image: CaptureImage) -> None:
    await db.delete(image)
    await db.commit()


async def update_capture_image(db: AsyncSession, image: CaptureImage, **kwargs) -> CaptureImage:
    for k, v in kwargs.items():
        setattr(image, k, v)
    await db.commit()
    await db.refresh(image)
    return image


async def count_images_for_capture(db: AsyncSession, capture_id: str) -> int:
    result = await db.execute(
        select(CaptureImage).where(CaptureImage.capture_id == capture_id)
    )
    return len(result.scalars().all())


# ── Annotation ────────────────────────────────────────────

async def create_annotation(
    db: AsyncSession, capture_image_id: str, region_json: dict | None = None, note: str = ""
) -> Annotation:
    ann = Annotation(capture_image_id=capture_image_id, region_json=region_json, note=note)
    db.add(ann)
    await db.commit()
    await db.refresh(ann)
    return ann


# ── Comparison ────────────────────────────────────────────

async def create_comparison(
    db: AsyncSession, room: str, move_in_capture_id: str, move_out_capture_id: str
) -> Comparison:
    comp = Comparison(
        room=room,
        move_in_capture_id=move_in_capture_id,
        move_out_capture_id=move_out_capture_id,
    )
    db.add(comp)
    await db.commit()
    await db.refresh(comp)
    return comp


async def get_comparison(db: AsyncSession, comparison_id: str) -> Comparison | None:
    return await db.get(Comparison, comparison_id)


async def update_comparison(db: AsyncSession, comparison: Comparison, **kwargs) -> Comparison:
    for k, v in kwargs.items():
        setattr(comparison, k, v)
    await db.commit()
    await db.refresh(comparison)
    return comparison


async def list_comparisons_for_property(db: AsyncSession, property_id: str) -> list[Comparison]:
    """Get all comparisons across all sessions for a property."""
    result = await db.execute(
        select(Comparison)
        .join(Capture, Comparison.move_in_capture_id == Capture.id)
        .join(Session, Capture.session_id == Session.id)
        .where(Session.property_id == property_id)
        .order_by(Comparison.created_at)
    )
    return list(result.scalars().all())


# ── Candidate ─────────────────────────────────────────────

async def create_candidate(
    db: AsyncSession,
    comparison_id: str,
    region_json: dict | None = None,
    confidence: float = 0.0,
    reason_codes: list[str] | None = None,
    crop_path: str = "",
) -> Candidate:
    cand = Candidate(
        comparison_id=comparison_id,
        region_json=region_json,
        confidence=confidence,
        reason_codes=reason_codes,
        crop_path=crop_path,
    )
    db.add(cand)
    await db.commit()
    await db.refresh(cand)
    return cand


async def get_candidate(db: AsyncSession, candidate_id: str) -> Candidate | None:
    return await db.get(Candidate, candidate_id)


async def update_candidate(db: AsyncSession, candidate: Candidate, **kwargs) -> Candidate:
    for k, v in kwargs.items():
        setattr(candidate, k, v)
    await db.commit()
    await db.refresh(candidate)
    return candidate
