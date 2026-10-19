import asyncio
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError
from starlette.concurrency import run_in_threadpool

from app.database import SessionLocal
from app.models.user import User
from app.auth.jwt_handler import decode_access_token
from app.ws import manager

router = APIRouter(tags=["Live"])


def authenticate(first_message) -> str | None:
    if not isinstance(first_message, dict) or first_message.get("type") != "auth":
        return None
    try:
        payload = decode_access_token(first_message.get("token", ""))
        user_id = uuid.UUID(payload.get("sub"))
    except (JWTError, ValueError, TypeError):
        return None

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            return None
        return str(user.id)
    finally:
        db.close()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    try:
        first_message = await asyncio.wait_for(websocket.receive_json(), timeout=10)
    except (asyncio.TimeoutError, WebSocketDisconnect, ValueError):
        await websocket.close(code=1008)
        return

    user_id = await run_in_threadpool(authenticate, first_message)
    if user_id is None:
        await websocket.close(code=1008)
        return

    manager.register(user_id, websocket)
    await websocket.send_json({"type": "ready"})

    try:
        while True:
            await websocket.receive_text()  # keeps the line open; we ignore anything the client sends
    except WebSocketDisconnect:
        pass
    finally:
        manager.unregister(user_id, websocket)