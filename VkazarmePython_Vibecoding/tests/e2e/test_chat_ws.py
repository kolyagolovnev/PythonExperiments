"""End-to-end tests for the realtime WebSocket channel /ws/chats/{ChatID}.

Sync tests with starlette's TestClient (it owns the ASGI websocket loop).
REST remains the write path: a POST .../messages must arrive as a
newMessage envelope on every subscriber's socket.
"""

from fastapi.testclient import TestClient
from starlette.testclient import WebSocketDisconnect

from tests.conftest import bearer


def _setup(client: TestClient) -> dict[str, str]:
    for email in ("a@t.com", "b@t.com", "c@t.com"):
        client.post("/account/signup", json={"email": email, "password": "Password123"})
    return {
        "a": client.post("/account/signin",
                         json={"email": "a@t.com", "password": "Password123"}).json(),
        "b": client.post("/account/signin",
                         json={"email": "b@t.com", "password": "Password123"}).json(),
        "c": client.post("/account/signin",
                         json={"email": "c@t.com", "password": "Password123"}).json(),
    }


def _open_chat(client: TestClient, token: str, body: dict) -> int:
    client.post("/chats", json=body, headers=bearer(token))
    chats = client.get("/chats", headers=bearer(token)).json()
    return chats[0]["id"]


def test_member_receives_rest_messages_in_realtime(app):
    client = TestClient(app)
    tokens = _setup(client)
    chat_id = _open_chat(client, tokens["a"], {"chat_type": "personal", "users": [2]})

    with client.websocket_connect(f"/ws/chats/{chat_id}?token={tokens['b']}") as ws:
        ws.send_json({"type": "subscribe", "chatId": chat_id})

        response = client.post(f"/chats/{chat_id}/messages", json={"text": "hello!"},
                               headers=bearer(tokens["a"]))
        assert response.status_code == 200

        event = ws.receive_json()
        assert event["type"] == "newMessage"
        assert event["chatId"] == chat_id
        assert event["payload"]["text"] == "hello!"
        assert event["payload"]["user_id"] == 1
        assert "id" in event["payload"] and "time" in event["payload"]


def test_all_subscribers_receive_the_message(app):
    client = TestClient(app)
    tokens = _setup(client)
    chat_id = _open_chat(client, tokens["a"],
                         {"chat_type": "public", "name": "Reunion", "users": [2, 3]})

    with client.websocket_connect(f"/ws/chats/{chat_id}?token={tokens['b']}") as ws_b, \
         client.websocket_connect(f"/ws/chats/{chat_id}?token={tokens['c']}") as ws_c:
        ws_b.send_json({"type": "subscribe", "chatId": chat_id})
        ws_c.send_json({"type": "subscribe", "chatId": chat_id})

        client.post(f"/chats/{chat_id}/messages", json={"text": "all hands"},
                    headers=bearer(tokens["a"]))
        assert ws_b.receive_json()["payload"]["text"] == "all hands"
        assert ws_c.receive_json()["payload"]["text"] == "all hands"


def test_member_change_events_reach_subscribers(app):
    client = TestClient(app)
    tokens = _setup(client)
    chat_id = _open_chat(client, tokens["a"],
                         {"chat_type": "public", "name": "Reunion", "users": [2]})

    with client.websocket_connect(f"/ws/chats/{chat_id}?token={tokens['b']}") as ws:
        ws.send_json({"type": "subscribe", "chatId": chat_id})

        client.post(f"/chats/{chat_id}/members", json={"user_id": 3},
                    headers=bearer(tokens["a"]))
        joined = ws.receive_json()
        assert joined == {"type": "memberChange", "chatId": chat_id,
                          "payload": {"action": "joined", "userId": 3, "role": "member"}}

        client.delete(f"/chats/{chat_id}/members/3", headers=bearer(tokens["a"]))
        kicked = ws.receive_json()
        assert kicked["payload"]["action"] == "kicked"
        assert kicked["payload"]["userId"] == 3


def test_ping_answered_with_pong(app):
    client = TestClient(app)
    tokens = _setup(client)
    chat_id = _open_chat(client, tokens["a"], {"chat_type": "personal", "users": [2]})

    with client.websocket_connect(f"/ws/chats/{chat_id}?token={tokens['a']}") as ws:
        ws.send_json({"type": "subscribe", "chatId": chat_id})
        ws.send_json({"type": "ping"})
        assert ws.receive_json() == {"type": "pong"}


def _closed(app, url: str, frame: dict) -> int:
    client = TestClient(app)
    with client.websocket_connect(url) as ws:
        ws.send_json(frame)
        try:
            ws.receive_json()
        except WebSocketDisconnect as disconnect:
            return disconnect.code
    raise AssertionError("connection was not closed")


def test_stranger_is_closed_with_4403(app):
    client = TestClient(app)
    tokens = _setup(client)
    chat_id = _open_chat(client, tokens["a"], {"chat_type": "personal", "users": [2]})
    # user 3 is not a member
    code = _closed(app, f"/ws/chats/{chat_id}?token={tokens['c']}",
                   {"type": "subscribe", "chatId": chat_id})
    assert code == 4403


def test_invalid_token_is_closed_with_4401(app):
    code = _closed(app, "/ws/chats/1?token=garbage.token.here",
                   {"type": "subscribe", "chatId": 1})
    assert code == 4401


def test_unknown_chat_is_closed_with_4404(app):
    client = TestClient(app)
    tokens = _setup(client)
    code = _closed(app, "/ws/chats/999?token=" + tokens["a"],
                   {"type": "subscribe", "chatId": 999})
    assert code == 4404


def test_bad_subscribe_frame_is_closed_with_4400(app):
    client = TestClient(app)
    tokens = _setup(client)
    chat_id = _open_chat(client, tokens["a"], {"chat_type": "personal", "users": [2]})
    code = _closed(app, f"/ws/chats/{chat_id}?token={tokens['a']}",
                   {"type": "wrong", "chatId": chat_id})
    assert code == 4400


def test_subscribe_to_a_different_chat_id_is_closed_with_4400(app):
    client = TestClient(app)
    tokens = _setup(client)
    chat_id = _open_chat(client, tokens["a"], {"chat_type": "personal", "users": [2]})
    code = _closed(app, f"/ws/chats/{chat_id}?token={tokens['a']}",
                   {"type": "subscribe", "chatId": chat_id + 1})
    assert code == 4400
