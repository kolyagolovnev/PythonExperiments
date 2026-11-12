import pytest

def test_chat_lifecycle(client, headers, auth_token):
    # Given: два пользователя
    resp_users = client.get("/users", headers=headers, params={"limit": 2})
    users = resp_users.json()
    if len(users) < 2:
        pytest.skip("Not enough users for chat test")
    u1, u2 = users[0], users[1]

    # When: создаём чат между ними
    chat_data = {"participants": [u1["id"], u2["id"]]}
    resp_create = client.post("/chats", json=chat_data, headers=headers)
    assert resp_create.status_code in (200, 201)
    chat = resp_create.json()
    chat_id = chat["id"]

    # Then: чат существует
    resp_get = client.get(f"/chats/{chat_id}", headers=headers)
    assert resp_get.status_code == 200

    # When: отправляем сообщение
    msg_data = {"content": "Привет, сослуживец!", "sender_id": u1["id"]}
    resp_msg = client.post(f"/chats/{chat_id}/messages", json=msg_data, headers=headers)
    assert resp_msg.status_code in (200, 201)

    # Then: сообщение видно
    resp_msgs = client.get(f"/chats/{chat_id}/messages", headers=headers)
    assert resp_msgs.status_code == 200
    msgs = resp_msgs.json()
    assert len(msgs) >= 1
