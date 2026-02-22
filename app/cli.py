"""CLI for Walkthru-X — bootstrap companies, manage data."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys


async def cmd_create_company(args):
    """Create a new company with an admin user."""
    from app.db.auth_engine import auth_engine, auth_session_factory
    from app.models.auth_models import AuthBase
    from app.services.company_bootstrap import create_company

    # Ensure auth tables exist
    async with auth_engine.begin() as conn:
        await conn.run_sync(AuthBase.metadata.create_all)

    # Get password interactively if not provided
    password = args.password
    if not password:
        password = getpass.getpass("Admin password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords do not match")
            sys.exit(1)

    if len(password) < 8:
        print("Password must be at least 8 characters")
        sys.exit(1)

    async with auth_session_factory() as db:
        company, admin = await create_company(
            name=args.name,
            admin_email=args.email,
            admin_password=password,
            auth_db=db,
            admin_display_name=args.display_name or "",
        )

    print(f"Company created: {company.name} (id={company.id}, slug={company.slug})")
    print(f"Admin user: {admin.email} (id={admin.id})")
    print(f"Tenant DB: data/companies/{company.id}/tenant.db")


async def cmd_migrate(args):
    """Migrate data from legacy walkthrough.db to multi-tenant structure."""
    from pathlib import Path
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import select, text

    from app.db.auth_engine import auth_engine, auth_session_factory
    from app.db.engine import tenant_pool
    from app.models.auth_models import AuthBase
    from app.models.base import Base
    from app.services.company_bootstrap import create_company
    from app.db import crud

    legacy_db_path = Path("data/walkthrough.db")
    if not legacy_db_path.exists():
        print("No legacy database found at data/walkthrough.db")
        sys.exit(1)

    # Ensure auth tables exist
    async with auth_engine.begin() as conn:
        await conn.run_sync(AuthBase.metadata.create_all)

    # Read legacy data
    legacy_engine = create_async_engine("sqlite+aiosqlite:///data/walkthrough.db", echo=False)
    legacy_factory = async_sessionmaker(legacy_engine, class_=AsyncSession, expire_on_commit=False)

    async with legacy_factory() as legacy_db:
        # Get owner info
        result = await legacy_db.execute(text("SELECT id, username, password_hash FROM owners LIMIT 1"))
        owner_row = result.first()
        if not owner_row:
            print("No owner found in legacy database")
            sys.exit(1)

        owner_id = owner_row[0]
        owner_username = owner_row[1]
        owner_password_hash = owner_row[2]

    # Create company + admin from legacy owner
    company_name = args.company_name or "My Company"
    admin_email = args.admin_email or f"{owner_username}@localhost"

    async with auth_session_factory() as auth_db:
        from app.models.auth_models import Company, User
        from app.services.auth import hash_password

        # Create company
        from app.services.company_bootstrap import _slugify
        slug = _slugify(company_name)
        company = Company(name=company_name, slug=slug)
        auth_db.add(company)
        await auth_db.flush()

        # Create admin user with the old password hash
        admin = User(
            company_id=company.id,
            email=admin_email,
            display_name=owner_username,
            password_hash=owner_password_hash,  # Reuse existing bcrypt hash
            role="admin",
        )
        auth_db.add(admin)
        await auth_db.commit()
        await auth_db.refresh(company)
        await auth_db.refresh(admin)

    # Create tenant DB
    from app.db.engine import create_tenant_db
    await create_tenant_db(company.id)

    # Copy data from legacy DB to tenant DB
    # We'll copy: properties, sessions, captures, capture_images, annotations,
    # comparisons, candidates, tenant_links, room_templates, owner_settings
    tables_to_copy = [
        "properties", "room_templates", "sessions", "tenant_links",
        "captures", "capture_images", "annotations",
        "comparisons", "candidates",
    ]

    tenant_engine = tenant_pool.get_engine(company.id)

    async with legacy_factory() as legacy_db:
        async with tenant_pool.session_factory(company.id)() as tenant_db:
            for table_name in tables_to_copy:
                try:
                    result = await legacy_db.execute(text(f"SELECT * FROM {table_name}"))
                    rows = result.fetchall()
                    columns = result.keys()

                    for row in rows:
                        row_dict = dict(zip(columns, row))
                        # Remove owner_id from properties (no longer needed)
                        row_dict.pop("owner_id", None)

                        cols = ", ".join(row_dict.keys())
                        placeholders = ", ".join(f":{k}" for k in row_dict.keys())
                        await tenant_db.execute(
                            text(f"INSERT OR IGNORE INTO {table_name} ({cols}) VALUES ({placeholders})"),
                            row_dict,
                        )

                    print(f"  Copied {len(rows)} rows from {table_name}")
                except Exception as e:
                    print(f"  Skipping {table_name}: {e}")

            # Copy owner_settings as company_settings
            try:
                result = await legacy_db.execute(
                    text("SELECT * FROM owner_settings WHERE owner_id = :oid"),
                    {"oid": owner_id},
                )
                settings_row = result.first()
                if settings_row:
                    settings_dict = dict(zip(result.keys(), settings_row))
                    settings_dict.pop("owner_id", None)
                    cols = ", ".join(settings_dict.keys())
                    placeholders = ", ".join(f":{k}" for k in settings_dict.keys())
                    await tenant_db.execute(
                        text(f"INSERT OR IGNORE INTO company_settings ({cols}) VALUES ({placeholders})"),
                        settings_dict,
                    )
                    print("  Copied owner_settings -> company_settings")
            except Exception as e:
                print(f"  Skipping owner_settings: {e}")
                # Create default settings
                await crud.create_company_settings(tenant_db)

            await tenant_db.commit()

    # Move images to company directory
    import shutil
    legacy_images = Path("data/images")
    company_images = Path(f"data/companies/{company.id}/images")
    if legacy_images.exists() and any(legacy_images.iterdir()):
        company_images.mkdir(parents=True, exist_ok=True)
        for item in legacy_images.iterdir():
            if item.is_dir():
                dest = company_images / item.name
                if not dest.exists():
                    shutil.copytree(str(item), str(dest))
        print(f"  Copied images to {company_images}")

    await legacy_engine.dispose()

    print(f"\nMigration complete!")
    print(f"  Company: {company.name} (id={company.id})")
    print(f"  Admin: {admin.email}")
    print(f"  Tenant DB: data/companies/{company.id}/tenant.db")
    print(f"\nYou can now log in with: {admin.email}")


async def cmd_encrypt_existing(args):
    """Encrypt existing plaintext DB fields and image files."""
    import os
    from pathlib import Path
    from sqlalchemy import select, text
    from app.services.encryption import encrypt_value, encrypt_bytes

    fernet_key = os.environ.get("FERNET_KEY", "")
    if not fernet_key:
        print("ERROR: FERNET_KEY environment variable must be set.")
        print('Generate one with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"')
        sys.exit(1)

    from app.db.engine import tenant_pool
    from app.models.base import Base

    companies_dir = Path("data/companies")
    if not companies_dir.exists():
        print("No companies directory found.")
        return

    for company_dir in companies_dir.iterdir():
        if not company_dir.is_dir() or not (company_dir / "tenant.db").exists():
            continue

        company_id = company_dir.name
        print(f"\n--- Encrypting company: {company_id} ---")

        # Encrypt DB fields
        factory = tenant_pool.session_factory(company_id)
        async with factory() as db:
            # Properties — encrypt address
            rows = (await db.execute(text("SELECT id, address FROM properties"))).fetchall()
            for row in rows:
                val = row[1]
                if val and not val.startswith("gAAAAA"):  # Not already encrypted
                    encrypted = encrypt_value(val)
                    await db.execute(
                        text("UPDATE properties SET address = :addr WHERE id = :id"),
                        {"addr": encrypted, "id": row[0]},
                    )
                    print(f"  Encrypted property address: {row[0]}")

            # Sessions — encrypt tenant names
            rows = (await db.execute(text("SELECT id, tenant_name, tenant_name_2 FROM sessions"))).fetchall()
            for row in rows:
                updates = {}
                if row[1] and not row[1].startswith("gAAAAA"):
                    updates["tenant_name"] = encrypt_value(row[1])
                if row[2] and not row[2].startswith("gAAAAA"):
                    updates["tenant_name_2"] = encrypt_value(row[2])
                if updates:
                    sets = ", ".join(f"{k} = :{k}" for k in updates)
                    updates["id"] = row[0]
                    await db.execute(text(f"UPDATE sessions SET {sets} WHERE id = :id"), updates)
                    print(f"  Encrypted session tenant names: {row[0]}")

            # CompanySettings — encrypt API keys
            rows = (await db.execute(text(
                "SELECT id, openai_api_key, anthropic_api_key, gemini_api_key, grok_api_key FROM company_settings"
            ))).fetchall()
            for row in rows:
                updates = {}
                for i, col in enumerate(["openai_api_key", "anthropic_api_key", "gemini_api_key", "grok_api_key"], 1):
                    val = row[i]
                    if val and not val.startswith("gAAAAA"):
                        updates[col] = encrypt_value(val)
                if updates:
                    sets = ", ".join(f"{k} = :{k}" for k in updates)
                    updates["id"] = row[0]
                    await db.execute(text(f"UPDATE company_settings SET {sets} WHERE id = :id"), updates)
                    print(f"  Encrypted API keys: {row[0]}")

            await db.commit()

        # Encrypt image files
        images_dir = company_dir / "images"
        if not images_dir.exists():
            continue

        for img_file in images_dir.rglob("*"):
            if img_file.is_file() and img_file.suffix != ".enc" and not (img_file.parent / f"{img_file.name}.enc").exists():
                try:
                    raw = img_file.read_bytes()
                    enc = encrypt_bytes(raw)
                    enc_path = img_file.parent / f"{img_file.name}.enc"
                    enc_path.write_bytes(enc)
                    img_file.unlink()  # Remove plaintext original
                    print(f"  Encrypted image: {img_file.relative_to(companies_dir)}")
                except Exception as e:
                    print(f"  WARNING: Failed to encrypt {img_file}: {e}")

    print("\nEncryption migration complete.")


def main():
    parser = argparse.ArgumentParser(description="Walkthru-X CLI")
    subparsers = parser.add_subparsers(dest="command")

    # create-company
    cc = subparsers.add_parser("create-company", help="Create a new company")
    cc.add_argument("--name", required=True, help="Company name")
    cc.add_argument("--email", required=True, help="Admin email")
    cc.add_argument("--password", default="", help="Admin password (prompted if not given)")
    cc.add_argument("--display-name", default="", help="Admin display name")

    # migrate
    mg = subparsers.add_parser("migrate", help="Migrate from legacy walkthrough.db")
    mg.add_argument("--company-name", default="My Company", help="Name for the migrated company")
    mg.add_argument("--admin-email", default="", help="Admin email (defaults to username@localhost)")

    # encrypt-existing
    subparsers.add_parser("encrypt-existing", help="Encrypt existing plaintext data (requires FERNET_KEY)")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "create-company":
        asyncio.run(cmd_create_company(args))
    elif args.command == "migrate":
        asyncio.run(cmd_migrate(args))
    elif args.command == "encrypt-existing":
        asyncio.run(cmd_encrypt_existing(args))


if __name__ == "__main__":
    main()
