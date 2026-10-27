
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
    if (
        not isinstance(first_message, dict)
        or first_message.get("type") != "auth"
    ):
        return None

    try:
        payload = decode_access_token(first_message.get("token", ""))
        user_id = uuid.UUID(payload.get("sub"))
    except (JWTError, ValueError, TypeError, AttributeError):
        return None

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()

        if not user or not user.is_active:
            return None

        return str(user.id)
    finally:
        db.close()


async def close_connection(websocket: WebSocket, code: int = 1008):
    """Close only if the WebSocket is still connected."""
    try:
        await websocket.close(code=code)
    except (WebSocketDisconnect, RuntimeError):
        # The client may have already disconnected.
        pass


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    # Step 1: Wait for the client's authentication message.
    try:
        first_message = await asyncio.wait_for(
            websocket.receive_json(),
            timeout=10,
        )

    except asyncio.TimeoutError:
        await close_connection(websocket, code=1008)
        return

    except WebSocketDisconnect:
        # The client disconnected before authenticating.
        return

    except ValueError:
        # The initial message was not valid JSON.
        await close_connection(websocket, code=1008)
        return

    # Step 2: Authenticate without blocking the async event loop.
    user_id = await run_in_threadpool(authenticate, first_message)

    if user_id is None:
        await close_connection(websocket, code=1008)
        return

    # Step 3: Register the authenticated connection.
    manager.register(user_id, websocket)

    try:
        await websocket.send_json({"type": "ready"})

        # Step 4: Keep the connection alive until the client disconnects.
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        # Normal client disconnection.
        pass

    finally:
        manager.unregister(user_id, websocket)
