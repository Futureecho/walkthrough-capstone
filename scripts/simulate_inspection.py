"""Simulate a complete tenant inspection for end-to-end testing.

Creates a property with rooms, downloads real interior photos from Pexels,
creates a move-in session with captures and concerns, then submits the
report to pending_review status so the owner can test the review workflow.

Usage:
    cd /home/verentyx/walkthrough
    FERNET_KEY=... venv/bin/python scripts/simulate_inspection.py
"""

import asyncio
import os
import sys
import secrets
from datetime import datetime, timezone, timedelta
from pathlib import Path
from io import BytesIO

import httpx
from ulid import ULID

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.engine import tenant_pool
from app.services.image_store import save_image
from app.models.property import Property
from app.models.session import Session
from app.models.capture import Capture
from app.models.capture_image import CaptureImage
from app.models.concern import Concern
from app.models.room_template import RoomTemplate
from app.models.tenant_link import TenantLink

COMPANY_ID = "01KJ28GASQR3423D4DGXYYCBB2"

# Pexels free images — wide-angle interior shots
ROOM_PHOTOS = {
    "Living Room": [
        "https://images.pexels.com/photos/8092427/pexels-photo-8092427.jpeg?auto=compress&w=1200",
        "https://images.pexels.com/photos/1510173/pexels-photo-1510173.jpeg?auto=compress&w=1200",
        "https://images.pexels.com/photos/6035357/pexels-photo-6035357.jpeg?auto=compress&w=1200",
    ],
    "Kitchen": [
        "https://images.pexels.com/photos/2089698/pexels-photo-2089698.jpeg?auto=compress&w=1200",
        "https://images.pexels.com/photos/6301185/pexels-photo-6301185.jpeg?auto=compress&w=1200",
        "https://images.pexels.com/photos/1080721/pexels-photo-1080721.jpeg?auto=compress&w=1200",
    ],
    "Bedroom": [
        "https://images.pexels.com/photos/7614416/pexels-photo-7614416.jpeg?auto=compress&w=1200",
        "https://images.pexels.com/photos/2983198/pexels-photo-2983198.jpeg?auto=compress&w=1200",
        "https://images.pexels.com/photos/271624/pexels-photo-271624.jpeg?auto=compress&w=1200",
    ],
    "Bathroom": [
        "https://images.pexels.com/photos/6920614/pexels-photo-6920614.jpeg?auto=compress&w=1200",
        "https://images.pexels.com/photos/5825561/pexels-photo-5825561.jpeg?auto=compress&w=1200",
        "https://images.pexels.com/photos/1457847/pexels-photo-1457847.jpeg?auto=compress&w=1200",
    ],
}

# Simulated concerns (title, description, room)
CONCERNS = [
    ("Scuffed baseboard", "Noticeable scuff marks along the baseboard near the entry, approximately 6 inches long.", "Living Room"),
    ("Cracked outlet cover", "The outlet cover plate on the south wall is cracked and loose.", "Kitchen"),
    ("Stain on ceiling", "Water stain on ceiling near the window, about 8 inches in diameter. Appears old.", "Bathroom"),
]


def ulid() -> str:
    return str(ULID())


async def download_photos() -> dict[str, list[bytes]]:
    """Download all room photos from Pexels."""
    result: dict[str, list[bytes]] = {}
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for room, urls in ROOM_PHOTOS.items():
            result[room] = []
            for url in urls:
                print(f"  Downloading {room} photo... ", end="", flush=True)
                try:
                    r = await client.get(url)
                    r.raise_for_status()
                    result[room].append(r.content)
                    print(f"{len(r.content) // 1024}KB")
                except Exception as e:
                    print(f"FAILED: {e}")
    return result


async def main():
    print("=== Walkthru-X Inspection Simulator ===\n")

    # 1. Download photos
    print("1. Downloading interior photos from Pexels...")
    photos = await download_photos()
    total_photos = sum(len(v) for v in photos.values())
    print(f"   Downloaded {total_photos} photos\n")

    if total_photos == 0:
        print("No photos downloaded, aborting.")
        return

    # 2. Create property & session via SQLAlchemy
    print("2. Creating property and inspection session...")

    factory = tenant_pool.session_factory(COMPANY_ID)
    async with factory() as db:
        # Create property
        prop = Property(
            id=ulid(),
            label="742 Evergreen Terrace",
            rooms=["Living Room", "Kitchen", "Bedroom", "Bathroom"],
            address="742 Evergreen Terrace, Springfield, IL 62704",
        )
        db.add(prop)
        await db.flush()
        print(f"   Property: {prop.label} ({prop.id})")

        # Create room templates
        for i, room_name in enumerate(["Living Room", "Kitchen", "Bedroom", "Bathroom"]):
            rt = RoomTemplate(
                id=ulid(),
                property_id=prop.id,
                name=room_name,
                display_order=i,
                capture_mode="traditional",
            )
            db.add(rt)
        await db.flush()
        print(f"   Room templates created")

        # Create session (move_in)
        session = Session(
            id=ulid(),
            property_id=prop.id,
            type="move_in",
            tenant_name="Alex Rivera",
            report_status="active",
        )
        db.add(session)
        await db.flush()
        print(f"   Session: {session.type} ({session.id})")

        # Create tenant link
        token = f"{COMPANY_ID}:{secrets.token_urlsafe(48)}"
        link = TenantLink(
            id=ulid(),
            session_id=session.id,
            token=token,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            is_active=True,
        )
        db.add(link)
        await db.flush()
        print(f"   Tenant link created")

        # 3. Create captures with photos
        print("\n3. Creating room captures with photos...")
        for room_name, room_photos in photos.items():
            capture = Capture(
                id=ulid(),
                session_id=session.id,
                room=room_name,
                status="passed",  # Simulate passing quality gate
                metrics_json={"overall": "pass", "simulated": True},
            )
            db.add(capture)
            await db.flush()

            for seq, photo_bytes in enumerate(room_photos, 1):
                orig_path, thumb_path = await save_image(
                    photo_bytes, capture.id, seq, ".jpg", COMPANY_ID
                )
                ci = CaptureImage(
                    id=ulid(),
                    capture_id=capture.id,
                    seq=seq,
                    file_path=orig_path,
                    thumbnail_path=thumb_path,
                    orientation_hint=f"position_{seq}",
                )
                db.add(ci)

            await db.flush()
            print(f"   {room_name}: {len(room_photos)} photos saved")

        # 4. Create concerns
        print("\n4. Creating tenant concerns...")
        for title, desc, room in CONCERNS:
            # Use first photo from the room as the concern image
            concern_photos = photos.get(room, [])
            file_path = ""
            thumb_path = ""
            if concern_photos:
                bucket = f"concerns_{session.id}"
                seq = CONCERNS.index((title, desc, room)) + 1
                file_path, thumb_path = await save_image(
                    concern_photos[0], bucket, seq, ".jpg", COMPANY_ID
                )

            concern = Concern(
                id=ulid(),
                session_id=session.id,
                room=room,
                title=title,
                description=desc,
                file_path=file_path,
                thumbnail_path=thumb_path,
            )
            db.add(concern)
            print(f"   [{room}] {title}")

        await db.flush()

        # 5. Submit report to pending_review
        print("\n5. Submitting report to review queue...")
        session.report_status = "pending_review"
        await db.commit()
        print(f"   Report status: pending_review")

        print(f"\n=== Simulation Complete ===")
        print(f"Property:  {prop.label}")
        print(f"Session:   {session.id}")
        print(f"Rooms:     {len(photos)} with {total_photos} photos")
        print(f"Concerns:  {len(CONCERNS)}")
        print(f"Status:    pending_review (in owner queue)")
        print(f"\nLog in as owner to see this in your review queue!")


if __name__ == "__main__":
    asyncio.run(main())
