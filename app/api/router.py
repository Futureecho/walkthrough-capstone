"""Central router that includes all sub-routers."""

from fastapi import APIRouter

from app.api.properties import router as properties_router
from app.api.sessions import router as sessions_router
from app.api.captures import router as captures_router
from app.api.comparisons import router as comparisons_router
from app.api.candidates import router as candidates_router
from app.api.reports import router as reports_router
from app.api.websocket import router as websocket_router
from app.api.auth import router as auth_router
from app.api.admin import router as admin_router
from app.api.invite import router as invite_router
from app.api.dashboard import router as dashboard_router
from app.api.room_templates import router as room_templates_router
from app.api.tenant import router as tenant_router
from app.api.technicians import router as technicians_router
from app.api.concerns import router as concerns_router
from app.api.work_orders import router as work_orders_router

api_router = APIRouter()
api_router.include_router(properties_router)
api_router.include_router(sessions_router)
api_router.include_router(captures_router)
api_router.include_router(comparisons_router)
api_router.include_router(candidates_router)
api_router.include_router(reports_router)
api_router.include_router(websocket_router)
api_router.include_router(auth_router)
api_router.include_router(admin_router)
api_router.include_router(invite_router)
api_router.include_router(dashboard_router)
api_router.include_router(room_templates_router)
api_router.include_router(tenant_router)
api_router.include_router(technicians_router)
api_router.include_router(concerns_router)
api_router.include_router(work_orders_router)
