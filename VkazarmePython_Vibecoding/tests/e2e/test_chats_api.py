"""End-to-end tests for /chats: chats, members, messages.

Covers the spec's status codes: 401 without a token, 403 for strangers,
404 for missing chats/memberships, 400 for bad bodies and duplicates.
"""

import pytest
from httpx import AsyncClient

from tests.conftest import bearer, sign_up_and_sign_in


@pytest.fixture
async def tokens(client: AsyncClient) -> dict[str, str]:
    return {
        "a": await sign_up_and_sign_in(client, "a@t.com"),  # user 1
        "b": await sign_up_and_sign_in(client, "b@t.com"),  # user 2
        "c": await sign_up_and_sign_in(client, "c@t.com"),  # user 3
    }


async def _created_chat_id(client: AsyncClient, tokens) -> int:
    """POST /chats returns an empty body (per spec), so the new chat's id
    is discovered from the creator's chat list (each test has fresh state)."""
    chats = (await client.get("/chats", headers=bearer(tokens["a"]))).json()
    return chats[0]["id"]


@pytest.fixture
async def personal_chat(client: AsyncClient, tokens) -> int:
    """A 1:1 chat between users 1 and 2."""
    response = await client.post("/chats",
                                 json={"chat_type": "personal", "users": [2]},
                                 headers=bearer(tokens["a"]))
    assert response.status_code == 200
    return await _created_chat_id(client, tokens)


@pytest.fixture
async def public_chat(client: AsyncClient, tokens) -> int:
    """A public chat owned by user 1 with user 2."""
    response = await client.post("/chats",
                                 json={"chat_type": "public", "name": "Reunion",
                                       "users": [2]},
                                 headers=bearer(tokens["a"]))
    assert response.status_code == 200
    return await _created_chat_id(client, tokens)


class TestAuth:

    async def test_requires_token(self, client: AsyncClient):
        for method, url in [("get", "/chats"), ("post", "/chats"),
                            ("get", "/chats/1"), ("get", "/chats/1/members"),
                            ("post", "/chats/1/members"),
                            ("delete", "/chats/1/members/1"),
                            ("get", "/chats/1/messages"),
                            ("post", "/chats/1/messages")]:
            response = await client.request(method, url, json={"text": "x"})
            assert response.status_code == 401, url


class TestCreateChats:

    async def test_personal_chat_is_listed_under_the_other_participant(
            self, client: AsyncClient, tokens, personal_chat):
        for_a = (await client.get("/chats", headers=bearer(tokens["a"]))).json()
        for_b = (await client.get("/chats", headers=bearer(tokens["b"]))).json()
        assert [chat["id"] for chat in for_a] == [personal_chat]
        assert for_a[0]["name"] == "Noname Nosurname"  # user 2's names, for user 1
        assert for_b[0]["name"] == "Noname Nosurname"  # user 1's names, for user 2

    async def test_personal_chat_creation_is_idempotent(self, client, tokens,
                                                        personal_chat):
        await client.post("/chats", json={"chat_type": "personal", "users": [1]},
                          headers=bearer(tokens["b"]))
        chats = (await client.get("/chats", headers=bearer(tokens["a"]))).json()
        assert len(chats) == 1

    async def test_personal_chat_with_two_others_is_400(self, client, tokens):
        response = await client.post("/chats",
                                     json={"chat_type": "personal", "users": [2, 3]},
                                     headers=bearer(tokens["a"]))
        assert response.status_code == 400

    async def test_personal_chat_with_unknown_user_is_404(self, client, tokens):
        response = await client.post("/chats",
                                     json={"chat_type": "personal", "users": [999]},
                                     headers=bearer(tokens["a"]))
        assert response.status_code == 404

    async def test_public_chat_with_members(self, client, tokens, public_chat):
        response = await client.get(f"/chats/{public_chat}", headers=bearer(tokens["a"]))
        assert response.status_code == 200
        body = response.json()
        assert body["chat_type"] == "public"
        assert body["name"] == "Reunion"

        members = (await client.get(f"/chats/{public_chat}/members",
                                    headers=bearer(tokens["a"]))).json()
        by_id = {member["user"]["id"]: member for member in members}
        assert by_id[1]["is_owner"] is True
        assert by_id[2]["is_owner"] is False


class TestMembershipRules:

    async def test_stranger_cannot_open_chat(self, client, tokens, personal_chat):
        response = await client.get(f"/chats/{personal_chat}", headers=bearer(tokens["c"]))
        assert response.status_code == 403

    async def test_unknown_chat_is_404(self, client, tokens):
        response = await client.get("/chats/999", headers=bearer(tokens["a"]))
        assert response.status_code == 404

    async def test_stranger_cannot_add_member(self, client, tokens, public_chat):
        response = await client.post(f"/chats/{public_chat}/members",
                                     json={"user_id": 3}, headers=bearer(tokens["c"]))
        assert response.status_code == 403

    async def test_member_adds_member(self, client, tokens, public_chat):
        response = await client.post(f"/chats/{public_chat}/members",
                                     json={"user_id": 3}, headers=bearer(tokens["b"]))
        assert response.status_code == 200
        members = (await client.get(f"/chats/{public_chat}/members",
                                    headers=bearer(tokens["a"]))).json()
        assert [member["user"]["id"] for member in members] == [1, 2, 3]

    async def test_duplicate_member_is_400(self, client, tokens, public_chat):
        response = await client.post(f"/chats/{public_chat}/members",
                                     json={"user_id": 2}, headers=bearer(tokens["a"]))
        assert response.status_code == 400

    async def test_unknown_user_is_404(self, client, tokens, public_chat):
        response = await client.post(f"/chats/{public_chat}/members",
                                     json={"user_id": 999}, headers=bearer(tokens["a"]))
        assert response.status_code == 404

    async def test_cannot_extend_personal_chat(self, client, tokens, personal_chat):
        response = await client.post(f"/chats/{personal_chat}/members",
                                     json={"user_id": 3}, headers=bearer(tokens["a"]))
        assert response.status_code == 403

    async def test_owner_removes_member(self, client, tokens, public_chat):
        response = await client.delete(f"/chats/{public_chat}/members/2",
                                       headers=bearer(tokens["a"]))
        assert response.status_code == 200
        members = (await client.get(f"/chats/{public_chat}/members",
                                    headers=bearer(tokens["a"]))).json()
        assert [member["user"]["id"] for member in members] == [1]

    async def test_member_leaves(self, client, tokens, public_chat):
        response = await client.delete(f"/chats/{public_chat}/members/2",
                                       headers=bearer(tokens["b"]))
        assert response.status_code == 200

    async def test_owner_cannot_be_removed_or_leave(self, client, tokens, public_chat):
        response = await client.delete(f"/chats/{public_chat}/members/1",
                                       headers=bearer(tokens["b"]))
        assert response.status_code == 403
        response = await client.delete(f"/chats/{public_chat}/members/1",
                                       headers=bearer(tokens["a"]))
        assert response.status_code == 403

    async def test_removing_non_member_is_404(self, client, tokens, public_chat):
        response = await client.delete(f"/chats/{public_chat}/members/3",
                                       headers=bearer(tokens["a"]))
        assert response.status_code == 404


class TestMessages:

    async def test_members_exchange_messages(self, client, tokens, personal_chat):
        await client.post(f"/chats/{personal_chat}/messages", json={"text": "hello"},
                          headers=bearer(tokens["a"]))
        await client.post(f"/chats/{personal_chat}/messages", json={"text": "hi!"},
                          headers=bearer(tokens["b"]))

        messages = (await client.get(f"/chats/{personal_chat}/messages",
                                     headers=bearer(tokens["a"]))).json()
        assert [message["text"] for message in messages] == ["hello", "hi!"]
        assert [message["user_id"] for message in messages] == [1, 2]
        assert "time" in messages[0]

    async def test_stranger_cannot_send_or_read(self, client, tokens, personal_chat):
        response = await client.post(f"/chats/{personal_chat}/messages",
                                     json={"text": "spam"}, headers=bearer(tokens["c"]))
        assert response.status_code == 403
        response = await client.get(f"/chats/{personal_chat}/messages",
                                    headers=bearer(tokens["c"]))
        assert response.status_code == 403

    async def test_empty_text_is_400(self, client, tokens, personal_chat):
        response = await client.post(f"/chats/{personal_chat}/messages",
                                     json={"text": ""}, headers=bearer(tokens["a"]))
        assert response.status_code == 400

    async def test_messages_of_unknown_chat_are_404(self, client, tokens):
        response = await client.get("/chats/999/messages", headers=bearer(tokens["a"]))
        assert response.status_code == 404


class TestUserDeletionCascade:

    async def test_deleting_user_removes_their_personal_chats(self, client, tokens,
                                                              container):
        await client.delete("/users/2", headers=bearer(tokens["c"]))
        chats = (await client.get("/chats", headers=bearer(tokens["a"]))).json()
        assert chats == []
