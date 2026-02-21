"""Seed the database with a demo property and rooms."""

import asyncio
from pathlib import Path

from app.db.engine import engine, async_session_factory
from app.models import Base
from app.db import crud


async def seed():
    # Ensure data directory exists
    Path("data/images").mkdir(parents=True, exist_ok=True)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as db:
        # Check if demo property already exists
        existing = await crud.list_properties(db)
        if any(p.label == "Demo Apartment 4B" for p in existing):
            print("Demo property already exists, skipping seed.")
            return

        prop = await crud.create_property(db, "Demo Apartment 4B", [
            "Living Room",
            "Kitchen",
            "Bedroom",
            "Bathroom",
        ])
        print(f"Created property: {prop.label} (id: {prop.id})")
        print(f"Rooms: {prop.rooms}")

        # Create a second demo property
        prop2 = await crud.create_property(db, "Unit 12A - Oak Street", [
            "Living Room",
            "Kitchen",
            "Master Bedroom",
            "Second Bedroom",
            "Bathroom",
            "Hallway",
        ])
        print(f"Created property: {prop2.label} (id: {prop2.id})")
        print(f"Rooms: {prop2.rooms}")

    print("\nSeed complete. Start the server with: make dev")
    print("Open http://localhost:8000 to begin.")


if __name__ == "__main__":
    asyncio.run(seed())
