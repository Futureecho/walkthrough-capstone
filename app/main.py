"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.db.engine import engine
from app.models import Base
from app.api.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Ensure data directories exist
    Path("data/images").mkdir(parents=True, exist_ok=True)
    yield


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
