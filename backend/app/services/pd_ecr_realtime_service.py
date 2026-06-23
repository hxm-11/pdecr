import uuid
from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class PdEcrConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[str, set[WebSocket]] = defaultdict(set)
        self.presence: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)

    async def connect(
        self,
        *,
        case_id: uuid.UUID,
        websocket: WebSocket,
        session_id: str,
        user_label: str,
    ) -> None:
        await websocket.accept()
        room = str(case_id)
        self.active_connections[room].add(websocket)
        self.presence[room][session_id] = {
            "session_id": session_id,
            "user_label": user_label,
            "module_id": None,
            "field_path": None,
        }
        await self.broadcast_presence(case_id=case_id)

    def disconnect(
        self, *, case_id: uuid.UUID, websocket: WebSocket, session_id: str
    ) -> None:
        room = str(case_id)
        self.active_connections[room].discard(websocket)
        self.presence[room].pop(session_id, None)

    async def broadcast(self, *, case_id: uuid.UUID, payload: dict[str, Any]) -> None:
        room = str(case_id)
        stale: list[WebSocket] = []
        for connection in list(self.active_connections[room]):
            try:
                await connection.send_json(payload)
            except Exception:
                stale.append(connection)
        for connection in stale:
            self.active_connections[room].discard(connection)

    async def broadcast_presence(self, *, case_id: uuid.UUID) -> None:
        room = str(case_id)
        await self.broadcast(
            case_id=case_id,
            payload={
                "type": "presence",
                "users": list(self.presence[room].values()),
            },
        )

    async def update_presence(
        self,
        *,
        case_id: uuid.UUID,
        session_id: str,
        module_id: str | None,
        field_path: str | None,
    ) -> None:
        room = str(case_id)
        if session_id in self.presence[room]:
            self.presence[room][session_id]["module_id"] = module_id
            self.presence[room][session_id]["field_path"] = field_path
        await self.broadcast_presence(case_id=case_id)


pd_ecr_connection_manager = PdEcrConnectionManager()
