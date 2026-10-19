from fastapi import WebSocket


class ConnectionManager:
    """Keeps track of which users are connected, so we can push messages to them."""

    def __init__(self):
        self._connections: dict[str, set[WebSocket]] = {}

    def register(self, user_id: str, ws: WebSocket) -> None:
        self._connections.setdefault(user_id, set()).add(ws)

    def unregister(self, user_id: str, ws: WebSocket) -> None:
        sockets = self._connections.get(user_id)
        if sockets:
            sockets.discard(ws)
            if not sockets:
                del self._connections[user_id]

    async def _send(self, ws: WebSocket, user_id: str, payload: dict) -> None:
        try:
            await ws.send_json(payload)
        except Exception:
            self.unregister(user_id, ws)  # the connection died, forget it

    async def send_to_users(self, user_ids, payload: dict) -> None:
        for uid in {str(u) for u in user_ids}:
            for ws in list(self._connections.get(uid, [])):
                await self._send(ws, uid, payload)

    async def broadcast(self, payload: dict) -> None:
        for uid, sockets in list(self._connections.items()):
            for ws in list(sockets):
                await self._send(ws, uid, payload)


manager = ConnectionManager()