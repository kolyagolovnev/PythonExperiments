"""WebSocket connection hub: keeps per-chat subscriber sets and pushes events.

Event envelopes follow the AsyncAPI contract (api_specification/asyncapi.yaml):
    {"type": "newMessage", "chatId": ..., "payload": {id, user_id, text, time}}
    {"type": "memberChange", "chatId": ..., "payload": {action, userId, role}}

The hub is stored per app instance (in the container), so tests get an
isolated hub with a fresh subscriber state. A per-connection lock keeps
concurrent publishes from interleaving frames on one socket.
"""

import asyncio
from dataclasses import dataclass, field

from fastapi import WebSocket

from app.domains import models as dm
from app.services.ports import ChatEventPublisher


@dataclass
class _Connection:
    user_id: int
    websocket: WebSocket
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class WebSocketHub(ChatEventPublisher):
    def __init__(self) -> None:
        self._subscribers: dict[int, list[_Connection]] = {}

    async def connect(self, chat_id: int, user_id: int, websocket: WebSocket) -> None:
        self._subscribers.setdefault(chat_id, []).append(
            _Connection(user_id=user_id, websocket=websocket)
        )

    async def disconnect(self, chat_id: int, user_id: int, websocket: WebSocket) -> None:
        connections = self._subscribers.get(chat_id, [])
        self._subscribers[chat_id] = [
            connection for connection in connections
            if connection.websocket is not websocket
        ]
        if not self._subscribers[chat_id]:
            self._subscribers.pop(chat_id, None)

    def subscriber_count(self, chat_id: int) -> int:
        return len(self._subscribers.get(chat_id, []))

    # --- ChatEventPublisher port ---

    async def publish_message(self, message: dm.Message) -> None:
        envelope = {
            "type": "newMessage",
            "chatId": message.chat_id,
            "payload": {
                "id": message.id,
                "user_id": message.author_id,
                "text": message.text,
                "time": message.time.isoformat(),
            },
        }
        await self._broadcast(message.chat_id, envelope)

    async def publish_member_change(self, chat_id: int, action: str,
                                    user_id: int) -> None:
        envelope = {
            "type": "memberChange",
            "chatId": chat_id,
            "payload": {
                "action": action,
                "userId": user_id,
                "role": "member",  # role resolution needs the chat; kept simple
            },
        }
        await self._broadcast(chat_id, envelope)

    # --- helpers ---

    async def _broadcast(self, chat_id: int, envelope: dict) -> None:
        for connection in list(self._subscribers.get(chat_id, [])):
            async with connection.lock:
                await connection.websocket.send_json(envelope)
