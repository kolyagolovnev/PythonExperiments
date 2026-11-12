"""HTTP end-to-end flows with the app running in database mode.

Same user-visible behavior as the in-memory e2e suite, but backed by the
SQLAlchemy repositories. Runs on SQLite and (Docker permitting) Postgres.
"""

import pytest
from app.domains import models as dm
from httpx import AsyncClient

from app.main import create_app
from tests.conftest import ADMIN_EMAIL, bearer, merge_patch_headers, sign_up_and_sign_in


@pytest.fixture
async def db_app(db_container):
    return create_app(db_container.settings, db_container)


@pytest.fixture
async def client(db_app) -> AsyncClient:
    import httpx

    transport = httpx.ASGITransport(app=db_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


@pytest.fixture
async def tokens(client: AsyncClient) -> dict[str, str]:
    return {
        "a": await sign_up_and_sign_in(client, "a@t.com"),
        "b": await sign_up_and_sign_in(client, "b@t.com"),
        "admin": await sign_up_and_sign_in(client, ADMIN_EMAIL),
    }


async def test_signup_signin_and_profile_flow(client: AsyncClient, tokens):
    response = await client.patch("/users/1", json={"name": "Ivan", "rang": 7},
                                  headers=merge_patch_headers(tokens["a"]))
    assert response.status_code == 200
    body = (await client.get("/users/1", headers=bearer(tokens["b"]))).json()
    assert (body["name"], body["rang"], body["surname"]) == ("Ivan", 7, "Nosurname")

    found = (await client.get("/users", params={"name": "ivan"},
                              headers=bearer(tokens["a"]))).json()
    assert [user["id"] for user in found] == [1]


async def test_friends_and_subscriptions_flow(client: AsyncClient, tokens,
                                              db_container):
    response = await client.post("/users/1/friends", json={"user_id": 2},
                                 headers=bearer(tokens["a"]))
    assert response.status_code == 200
    friends = (await client.get("/users/1/friends", headers=bearer(tokens["a"]))).json()
    assert [friend["id"] for friend in friends] == [2]

    group = await db_container.group_repo.add(dm.Group(id=0, name="209th Brigade"))
    response = await client.post("/users/1/subscriptions", json={"group_id": group.id},
                                 headers=bearer(tokens["a"]))
    assert response.status_code == 200
    subs = (await client.get("/users/1/subscriptions", headers=bearer(tokens["a"]))).json()
    assert subs[0]["name"] == "209th Brigade"


async def test_chat_and_message_flow(client: AsyncClient, tokens):
    response = await client.post("/chats",
                                 json={"chat_type": "personal", "users": [2]},
                                 headers=bearer(tokens["a"]))
    assert response.status_code == 200
    chat_id = (await client.get("/chats", headers=bearer(tokens["a"]))).json()[0]["id"]

    await client.post(f"/chats/{chat_id}/messages", json={"text": "privet"},
                      headers=bearer(tokens["a"]))
    messages = (await client.get(f"/chats/{chat_id}/messages",
                                 headers=bearer(tokens["b"]))).json()
    assert [message["text"] for message in messages] == ["privet"]
    assert messages[0]["user_id"] == 1


async def test_media_flow(client: AsyncClient, tokens):
    png = b"\x89PNG\r\n\x1a\n" + b"payload"
    upload = await client.post("/media", files={"file": ("a.png", png, "image/png")},
                               headers=bearer(tokens["a"]))
    assert upload.status_code == 200
    url = upload.json()["photo_url"]

    fetched = await client.get(url)
    assert fetched.status_code == 200
    assert fetched.content == png

    await client.delete("/users/1", headers=bearer(tokens["admin"]))
    assert (await client.get("/users/1", headers=bearer(tokens["admin"]))).status_code == 404
