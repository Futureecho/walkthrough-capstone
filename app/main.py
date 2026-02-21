"""FastAPI application entry point."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.db.engine import engine, async_session_factory
from app.models import Base
from app.api.router import api_router


async def _link_expiry_checker():
    """Background task: deactivate expired tenant links every 60 seconds."""
    from app.db import crud
    while True:
        try:
            async with async_session_factory() as db:
                expired = await crud.get_expired_active_links(db)
                for link in expired:
                    link.is_active = False
                    session = await crud.get_session(db, link.session_id)
                    if session and session.report_status == "active":
                        session.report_status = "pending_review"
                await db.commit()
        except Exception:
            pass  # Non-critical background task
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Ensure data directories exist
    Path("data/images").mkdir(parents=True, exist_ok=True)
    # Start background link expiry checker
    expiry_task = asyncio.create_task(_link_expiry_checker())
    yield
    expiry_task.cancel()


app = FastAPI(
    title="Walkthrough Capture System",
    description="Dispute-friendly move-in/move-out walkthrough capture with AI-powered quality, coverage, and comparison agents.",
    version="0.1.0",
    lifespan=lifespan,
)

# API routes
app.include_router(api_router)

# Static files (HTML/CSS/JS)
_static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

# Also serve images from data directory
Path("data/images").mkdir(parents=True, exist_ok=True)
app.mount("/data", StaticFiles(directory="data"), name="data")


@app.get("/")
async def root():
    return FileResponse(str(_static_dir / "index.html"))


@app.get("/capture")
async def capture_page():
    return FileResponse(str(_static_dir / "capture.html"))


@app.get("/review")
async def review_page():
    return FileResponse(str(_static_dir / "review.html"))


@app.get("/comparison")
async def comparison_page():
    return FileResponse(str(_static_dir / "comparison.html"))


# ── Owner portal pages ───────────────────────────────────

@app.get("/owner/login")
async def owner_login_page():
    return FileResponse(str(_static_dir / "owner-login.html"))


@app.get("/owner")
async def owner_dashboard_page():
    return FileResponse(str(_static_dir / "owner.html"))


@app.get("/owner/properties")
async def owner_properties_page():
    return FileResponse(str(_static_dir / "owner-property.html"))


@app.get("/owner/settings")
async def owner_settings_page():
    return FileResponse(str(_static_dir / "owner-settings.html"))


@app.get("/owner/reports/{session_id}")
async def owner_report_page(session_id: str):
    return FileResponse(str(_static_dir / "owner-report.html"))


# ── Tenant inspection page ───────────────────────────────

@app.get("/inspect/{token}")
async def tenant_inspect_page(token: str):
    return FileResponse(str(_static_dir / "tenant.html"))
