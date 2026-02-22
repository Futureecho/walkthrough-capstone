"""FastAPI application entry point."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response

from app.db.engine import engine, tenant_pool
from app.db.auth_engine import auth_engine
from app.models import Base, AuthBase
from app.api.router import api_router


async def _link_expiry_checker():
    """Background task: deactivate expired tenant links across all company DBs."""
    from app.db import crud

    while True:
        try:
            # Iterate all company DBs in the pool
            for company_id in list(tenant_pool._engines.keys()):
                try:
                    factory = tenant_pool.session_factory(company_id)
                    async with factory() as db:
                        expired = await crud.get_expired_active_links(db)
                        for link in expired:
                            link.is_active = False
                            session = await crud.get_session(db, link.session_id)
                            if session and session.report_status == "active":
                                session.report_status = "pending_review"
                        await db.commit()
                except Exception:
                    pass  # Skip failed company DBs
        except Exception:
            pass  # Non-critical background task
        await asyncio.sleep(60)


async def _init_existing_tenant_dbs():
    """On startup, warm the engine pool for all existing company dirs."""
    companies_dir = Path("data/companies")
    if not companies_dir.exists():
        return
    for company_dir in companies_dir.iterdir():
        if company_dir.is_dir() and (company_dir / "tenant.db").exists():
            tenant_pool.get_engine(company_dir.name)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create auth tables
    async with auth_engine.begin() as conn:
        await conn.run_sync(AuthBase.metadata.create_all)

    # Create legacy tables (kept for migration path)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Warm tenant engine pool for existing companies
    await _init_existing_tenant_dbs()

    # Ensure base data directories exist
    Path("data/companies").mkdir(parents=True, exist_ok=True)

    # Start background link expiry checker
    expiry_task = asyncio.create_task(_link_expiry_checker())
    yield
    expiry_task.cancel()
    await tenant_pool.dispose_all()


app = FastAPI(
    title="Walkthru-X",
    description="Dispute-friendly move-in/move-out walkthrough capture with AI-powered quality, coverage, and comparison agents.",
    version="0.2.0",
    lifespan=lifespan,
)

# API routes
app.include_router(api_router)

# Static files (HTML/CSS/JS)
_static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


# Authenticated image serving — decrypts encrypted images on the fly
@app.get("/data/companies/{company_id}/images/{path:path}")
async def serve_company_image(
    company_id: str,
    path: str,
    request: Request,
):
    """Serve images from the correct company directory (auth required)."""
    from app.dependencies import require_auth_or_tenant
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.db.auth_engine import get_auth_db

    # Authenticate: session cookie or tenant token
    async for db in get_auth_db():
        try:
            auth = await require_auth_or_tenant(request, request.query_params.get("token", ""), db)
        except HTTPException:
            raise HTTPException(401, "Authentication required")

    # Verify user belongs to this company
    if auth.company_id != company_id:
        raise HTTPException(403, "Access denied")

    # Read (and decrypt if needed) the image
    from app.services.image_store import read_image
    file_path = str(Path(f"data/companies/{company_id}/images/{path}"))
    try:
        image_data = await read_image(file_path)
    except FileNotFoundError:
        raise HTTPException(404, "Image not found")

    # Determine content type from extension
    ext = Path(path).suffix.lower().replace(".enc", "")
    if not ext:
        # Path might be like "001.jpg.enc" — extract the real extension
        stem = Path(path).stem
        ext = Path(stem).suffix.lower() if "." in stem else ".jpg"
    content_types = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
    content_type = content_types.get(ext, "image/jpeg")

    return Response(content=image_data, media_type=content_type)


@app.get("/")
async def root():
    return FileResponse(str(_static_dir / "landing.html"))


@app.get("/app")
async def app_page():
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


@app.get("/owner/position")
async def owner_position_page():
    return FileResponse(str(_static_dir / "owner-position.html"))


@app.get("/owner/settings")
async def owner_settings_page():
    return FileResponse(str(_static_dir / "owner-settings.html"))


@app.get("/owner/admin")
async def owner_admin_page():
    return FileResponse(str(_static_dir / "owner-admin.html"))


@app.get("/owner/reports/{session_id}")
async def owner_report_page(session_id: str):
    return FileResponse(str(_static_dir / "owner-report.html"))


# ── Invite + password reset pages ────────────────────────

@app.get("/invite/{token}")
async def invite_page(token: str):
    return FileResponse(str(_static_dir / "invite.html"))


@app.get("/join/{token}")
async def join_page(token: str):
    return FileResponse(str(_static_dir / "join.html"))


@app.get("/reset-password/{token}")
async def reset_password_page(token: str):
    return FileResponse(str(_static_dir / "reset-password.html"))


# ── Tenant inspection page ───────────────────────────────

@app.get("/inspect/{token:path}")
async def tenant_inspect_page(token: str):
    return FileResponse(str(_static_dir / "tenant.html"))
