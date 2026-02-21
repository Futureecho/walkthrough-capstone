"""Central router that includes all sub-routers."""

from fastapi import APIRouter

from app.api.properties import router as properties_router
from app.api.sessions import router as sessions_router
from app.api.captures import router as captures_router
from app.api.comparisons import router as comparisons_router
from app.api.candidates import router as candidates_router
from app.api.reports import router as reports_router
from app.api.websocket import router as websocket_router

api_router = APIRouter()
api_router.include_router(properties_router)
api_router.include_router(sessions_router)
api_router.include_router(captures_router)
api_router.include_router(comparisons_router)
api_router.include_router(candidates_router)
api_router.include_router(reports_router)
api_router.include_router(websocket_router)
