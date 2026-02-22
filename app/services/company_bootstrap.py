"""Bootstrap a new company: auth DB rows + tenant DB init."""

from __future__ import annotations

import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth_models import Company, User
from app.services.auth import hash_password
from app.db.engine import create_tenant_db
from app.db import crud


def _slugify(name: str) -> str:
    """Convert a company name to a URL-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')
    return slug or "company"


async def create_company(
    name: str,
    admin_email: str,
    admin_password: str,
    auth_db: AsyncSession,
    admin_display_name: str = "",
) -> tuple[Company, User]:
    """Create a new company + admin user + tenant DB.

    Returns (company, admin_user).
    """
    slug = _slugify(name)

    # Check for duplicate slug
    from sqlalchemy import select
    result = await auth_db.execute(select(Company).where(Company.slug == slug))
    existing = result.scalars().first()
    if existing:
        # Append a suffix
        slug = f"{slug}-{existing.id[:4]}"

    company = Company(name=name, slug=slug)
    auth_db.add(company)
    await auth_db.flush()  # Get the company ID

    admin = User(
        company_id=company.id,
        email=admin_email,
        display_name=admin_display_name or admin_email.split("@")[0],
        password_hash=hash_password(admin_password),
        role="admin",
    )
    auth_db.add(admin)
    await auth_db.commit()
    await auth_db.refresh(company)
    await auth_db.refresh(admin)

    # Create tenant DB with tables + default settings
    await create_tenant_db(company.id)

    from app.db.engine import tenant_pool
    factory = tenant_pool.session_factory(company.id)
    async with factory() as tenant_db:
        await crud.create_company_settings(tenant_db)

    return company, admin
