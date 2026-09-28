"""WebSocket endpoint for real-time sensor updates.

Clients connect via /api/v1/ws/sensors?token=<JWT> and receive broadcasts
when DeviceGateway reports new sensor values.
"""

import asyncio
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.core.logging import get_logger
from app.core.security import decode_token

logger = get_logger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections and broadcasts messages."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    @property
    def active_count(self) -> int:
        return len(self._connections)

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)
        logger.info("ws_client_connected", total=len(self._connections))

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._connections:
            self._connections.remove(ws)
        logger.info("ws_client_disconnected", total=len(self._connections))

    async def broadcast(self, data: dict[str, Any]) -> None:
        """Send data to all connected clients concurrently. Removes stale connections.

        Each send is bounded by a timeout so one slow client (bad WiFi) can't
        stall the others — or the gateway HTTP callback that triggered this.
        """
        message = json.dumps(data)
        targets = [ws for ws in self._connections if ws.client_state == WebSocketState.CONNECTED]

        async def _send(ws: WebSocket) -> WebSocket | None:
            try:
                await asyncio.wait_for(ws.send_text(message), timeout=2.0)
                return None
            except Exception:
                return ws

        results = await asyncio.gather(*(_send(ws) for ws in targets))
        for ws in results:
            if ws is not None:
                self.disconnect(ws)


# Singleton — shared across the app
manager = ConnectionManager()


def _authenticate_ws(token: str | None) -> str | None:
    """Validate JWT from query param. Returns username or None."""
    if not token:
        return None
    payload = decode_token(token)
    if payload is None or payload.get("type") != "access":
        return None
    return payload.get("sub")


@router.websocket("/sensors")
async def websocket_sensors(ws: WebSocket, token: str | None = None):
    """WebSocket endpoint for real-time sensor data.

    Authenticate via query param: ws://host/api/v1/ws/sensors?token=<JWT>
    """
    username = _authenticate_ws(token)
    if username is None:
        await ws.close(code=4001, reason="Authentication required")
        return

    await manager.connect(ws)
    try:
        # Keep connection alive — wait for client messages (ping/pong or close)
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(ws)
