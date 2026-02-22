from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.services.ws_manager import ws_manager
from app.services.auth import validate_session
from app.db.auth_engine import auth_session_factory

router = APIRouter(tags=["websocket"])


@router.websocket("/api/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(default=""),
):
    # Auth via query param token
    if token:
        async with auth_session_factory() as db:
            user = await validate_session(token, db)
            if not user:
                await websocket.close(code=4001, reason="Unauthorized")
                return
    # Allow unauthenticated WS for tenant-side (they use tenant link tokens)
    # The session_id itself provides scoping

    await ws_manager.connect(session_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(session_id, websocket)
