"""Generate HTML walkthrough report using Jinja2."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud
from app.models.property import Property

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
_env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=True)


async def generate_report(db: AsyncSession, prop: Property) -> str:
    """Generate an HTML report for a property."""
    sessions = await crud.list_sessions_for_property(db, prop.id)
    comparisons = await crud.list_comparisons_for_property(db, prop.id)

    template = _env.get_template("report.html.j2")
    return template.render(
        property=prop,
        sessions=sessions,
        comparisons=comparisons,
    )
