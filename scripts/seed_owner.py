"""Seed script to create the initial owner account."""

import asyncio
import sys
import getpass

# Ensure project root is on path
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from app.db.engine import engine, async_session_factory
from app.models import Base
from app.db import crud
from app.services.auth import hash_password


async def main():
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    username = input("Owner username: ").strip()
    if not username:
        print("Username cannot be empty.")
        return

    password = getpass.getpass("Owner password: ")
    if len(password) < 6:
        print("Password must be at least 6 characters.")
        return

    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match.")
        return

    async with async_session_factory() as db:
        existing = await crud.get_owner_by_username(db, username)
        if existing:
            print(f"Owner '{username}' already exists.")
            return

        pw_hash = hash_password(password)
        owner = await crud.create_owner(db, username, pw_hash)

        # Create default settings
        await crud.create_owner_settings(db, owner.id)

        print(f"Owner '{username}' created successfully (id={owner.id}).")


if __name__ == "__main__":
    asyncio.run(main())
