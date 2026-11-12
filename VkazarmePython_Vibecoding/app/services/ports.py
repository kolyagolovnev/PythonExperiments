"""Outbound ports the services call into (the inbound side of the layering).

Implementations live outside the services package: the WebSocket hub
(app/realtime) today, whatever comes later behind the same ABCs.
"""

from abc import ABC, abstractmethod

from app.domains import models as dm

# memberChange payload actions (see the AsyncAPI contract)
JOINED = "joined"
LEFT = "left"
KICKED = "kicked"


class ChatEventPublisher(ABC):
    """Delivers chat events to connected clients in realtime."""

    @abstractmethod
    async def publish_message(self, message: dm.Message) -> None:
        """Broadcasts a freshly saved chat message to the chat's subscribers."""

    @abstractmethod
    async def publish_member_change(self, chat_id: int, action: str,
                                    user_id: int) -> None:
        """Broadcasts a membership change (joined/left/kicked) of user_id."""
