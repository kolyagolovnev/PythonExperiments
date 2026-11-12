"""WebSocketHub unit tests with fake sockets, and ChatService event publishing."""

from datetime import datetime, timezone

import pytest

from app.container import build_container
from app.domains import models as dm
from app.realtime.hub import WebSocketHub
from app.services import exceptions as sex
from app.services.chat_service import ChatService
from app.services.ports import ChatEventPublisher, JOINED, KICKED, LEFT
from app.settings import Settings
from tests.conftest import TEST_SECRET, USER_PASSWORD


class FakeWebSocket:
    def __init__(self):
        self.sent: list[dict] = []

    async def send_json(self, data: dict) -> None:
        self.sent.append(data)


class RecordingPublisher(ChatEventPublisher):
    def __init__(self):
        self.messages: list[dm.Message] = []
        self.member_events: list[tuple[int, str, int]] = []

    async def publish_message(self, message: dm.Message) -> None:
        self.messages.append(message)

    async def publish_member_change(self, chat_id: int, action: str, user_id: int) -> None:
        self.member_events.append((chat_id, action, user_id))


class TestHub:

    async def test_subscribers_receive_message_envelope(self):
        hub = WebSocketHub()
        ws_a, ws_b = FakeWebSocket(), FakeWebSocket()
        await hub.connect(1, 1, ws_a)
        await hub.connect(1, 2, ws_b)

        message = dm.Message(id=7, chat_id=1, author_id=1, text="hi",
                             time=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
        await hub.publish_message(message)

        for ws in (ws_a, ws_b):
            assert ws.sent == [{
                "type": "newMessage",
                "chatId": 1,
                "payload": {"id": 7, "user_id": 1, "text": "hi",
                            "time": "2026-01-01T12:00:00+00:00"},
            }]

    async def test_other_chats_receive_nothing(self):
        hub = WebSocketHub()
        ws_other = FakeWebSocket()
        await hub.connect(2, 1, ws_other)
        await hub.publish_message(
            dm.Message(id=1, chat_id=1, author_id=1, text="x",
                       time=datetime(2026, 1, 1, tzinfo=timezone.utc)))
        assert ws_other.sent == []

    async def test_disconnect_stops_delivery(self):
        hub = WebSocketHub()
        ws = FakeWebSocket()
        await hub.connect(1, 1, ws)
        await hub.disconnect(1, 1, ws)
        assert hub.subscriber_count(1) == 0

        await hub.publish_message(
            dm.Message(id=1, chat_id=1, author_id=1, text="x",
                       time=datetime(2026, 1, 1, tzinfo=timezone.utc)))
        assert ws.sent == []

    async def test_member_change_envelope(self):
        hub = WebSocketHub()
        ws = FakeWebSocket()
        await hub.connect(1, 1, ws)
        await hub.publish_member_change(1, JOINED, 3)
        assert ws.sent == [{"type": "memberChange", "chatId": 1,
                            "payload": {"action": "joined", "userId": 3, "role": "member"}}]


@pytest.fixture
def container():
    return build_container(Settings(secret=TEST_SECRET))


@pytest.fixture
async def env(container):
    for email in ("a@t.com", "b@t.com"):
        await container.sign_service.sign_up(dm.SignUpData(email=email, password=USER_PASSWORD))

    def token_for(user_id: int) -> dm.AuthToken:
        return container.auth_service.issue_token(user_id, dm.Role.USER)

    return token_for


@pytest.fixture
def recording_service(container, env):
    """A ChatService identical to the container's but with a recording publisher."""
    publisher = RecordingPublisher()
    service = ChatService(
        container.chat_repo, container.chat_member_repo,
        container.message_repo, container.user_repo, publisher,
    )
    return service, publisher, env


class TestServicePublishing:

    async def test_send_message_publishes_new_message(self, recording_service):
        service, publisher, env = recording_service
        await service.create_chat(env(1), name="", chat_type=dm.ChatType.PERSONAL,
                                  users=[2], photo_url="")
        message = await service.send_message(env(1), 1, "hello")

        assert publisher.messages == [message]

    async def test_add_member_publishes_joined(self, recording_service):
        service, publisher, env = recording_service
        chat = await service.create_chat(env(1), name="Reunion",
                                         chat_type=dm.ChatType.PUBLIC, users=[], photo_url="")
        await service.add_member(env(1), chat.id, 2)
        assert publisher.member_events == [(chat.id, JOINED, 2)]

    async def test_remove_publishes_left_and_kicked(self, recording_service):
        service, publisher, env = recording_service
        chat = await service.create_chat(env(1), name="Reunion",
                                         chat_type=dm.ChatType.PUBLIC, users=[2], photo_url="")
        await service.remove_member(env(1), chat.id, 2)  # owner kicks
        await service.add_member(env(1), chat.id, 2)
        await service.remove_member(env(2), chat.id, 2)  # member leaves

        assert publisher.member_events == [
            (chat.id, KICKED, 2),
            (chat.id, JOINED, 2),
            (chat.id, LEFT, 2),
        ]

    async def test_failed_send_publishes_nothing(self, recording_service):
        service, publisher, env = recording_service
        with pytest.raises(Exception):  # repository ChatNotFound -> HTTP 404
            await service.send_message(env(1), 999, "spam")
        assert publisher.messages == []
