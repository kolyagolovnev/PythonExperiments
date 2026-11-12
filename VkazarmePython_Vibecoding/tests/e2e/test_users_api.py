"""End-to-end tests for /users: search, profile, friends, subscriptions.

Covers the spec's status codes: 401 without a token, 403 for foreign
profiles / non-admin actions, 404 for missing entities, 400 for bad data.
Topic groups for subscription tests are seeded through the container's
group repository (POST /groups belongs to a later milestone).
"""

import pytest
from httpx import AsyncClient

from app.domains import models as dm
from tests.conftest import (
    ADMIN_EMAIL,
    bearer,
    merge_patch_headers,
    sign_up_and_sign_in,
)


@pytest.fixture
async def tokens(client: AsyncClient) -> dict[str, str]:
    """Registers three users plus the admin; returns their bearer tokens."""
    return {
        "a": await sign_up_and_sign_in(client, "a@t.com"),
        "b": await sign_up_and_sign_in(client, "b@t.com"),
        "c": await sign_up_and_sign_in(client, "c@t.com"),
        "admin": await sign_up_and_sign_in(client, ADMIN_EMAIL),
    }


@pytest.fixture
async def topic_group(container):
    return await container.group_repo.add(dm.Group(id=0, name="209th Brigade"))


class TestSearchUsers:

    async def test_requires_token(self, client: AsyncClient):
        assert (await client.get("/users")).status_code == 401

    async def test_invalid_token_is_401(self, client: AsyncClient):
        response = await client.get("/users", headers=bearer("garbage.token.here"))
        assert response.status_code == 401

    async def test_lists_all_users(self, client: AsyncClient, tokens):
        response = await client.get("/users", headers=bearer(tokens["a"]))
        assert response.status_code == 200
        users = response.json()
        assert [user["id"] for user in users] == [1, 2, 3, 4]

    async def test_filters_by_name_and_surname(self, client: AsyncClient, tokens):
        await client.patch("/users/2", json={"name": "Boris", "surname": "Falko"},
                           headers=merge_patch_headers(tokens["b"]))
        response = await client.get("/users", params={"name": "bor"}, headers=bearer(tokens["a"]))
        assert [user["id"] for user in response.json()] == [2]

        response = await client.get("/users", params={"surname": "Fal"}, headers=bearer(tokens["a"]))
        assert [user["id"] for user in response.json()] == [2]

    async def test_limit_and_offset(self, client: AsyncClient, tokens):
        response = await client.get("/users", params={"limit": 2, "offset": 1},
                                    headers=bearer(tokens["a"]))
        assert [user["id"] for user in response.json()] == [2, 3]

    async def test_limit_out_of_range_is_400(self, client: AsyncClient, tokens):
        response = await client.get("/users", params={"limit": 1000}, headers=bearer(tokens["a"]))
        assert response.status_code == 400


class TestGetUser:

    async def test_requires_token(self, client: AsyncClient):
        assert (await client.get("/users/1")).status_code == 401

    async def test_returns_full_profile(self, client: AsyncClient, tokens):
        response = await client.get("/users/1", headers=bearer(tokens["b"]))
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == 1
        assert body["name"] == "Noname"
        assert body["job"] == "Unknown job"
        assert "personal_group_id" not in body  # only in list items, per spec

    async def test_unknown_user_is_404(self, client: AsyncClient, tokens):
        response = await client.get("/users/999", headers=bearer(tokens["a"]))
        assert response.status_code == 404


class TestPatchUser:

    async def test_requires_token(self, client: AsyncClient):
        response = await client.patch("/users/1", json={"name": "Alexander"},
                                      headers=merge_patch_headers("not-a-token"))
        assert response.status_code == 401

    async def test_own_profile_is_updated(self, client: AsyncClient, tokens):
        response = await client.patch("/users/1", json={"name": "Alexander", "rang": 5},
                                      headers=merge_patch_headers(tokens["a"]))
        assert response.status_code == 200
        body = (await client.get("/users/1", headers=bearer(tokens["a"]))).json()
        assert body["name"] == "Alexander"
        assert body["rang"] == 5
        assert body["surname"] == "Nosurname"  # untouched fields stay

    async def test_foreign_profile_is_403(self, client: AsyncClient, tokens):
        response = await client.patch("/users/2", json={"name": "Hacked"},
                                      headers=merge_patch_headers(tokens["a"]))
        assert response.status_code == 403

    async def test_unknown_user_is_404(self, client: AsyncClient, tokens):
        response = await client.patch("/users/999", json={"name": "X"},
                                      headers=merge_patch_headers(tokens["a"]))
        assert response.status_code == 404


class TestDeleteUser:

    async def test_requires_token(self, client: AsyncClient):
        assert (await client.delete("/users/1")).status_code == 401

    async def test_regular_user_is_403(self, client: AsyncClient, tokens):
        response = await client.delete("/users/2", headers=bearer(tokens["a"]))
        assert response.status_code == 403

    async def test_admin_can_delete(self, client: AsyncClient, tokens):
        response = await client.delete("/users/2", headers=bearer(tokens["admin"]))
        assert response.status_code == 200
        assert (await client.get("/users/2", headers=bearer(tokens["admin"]))).status_code == 404
        # the deleted user can no longer sign in
        response = await client.post("/account/signin",
                                     json={"email": "b@t.com", "password": "Password123"})
        assert response.status_code == 403

    async def test_unknown_user_is_404(self, client: AsyncClient, tokens):
        response = await client.delete("/users/999", headers=bearer(tokens["admin"]))
        assert response.status_code == 404


class TestFriends:

    async def test_requires_token(self, client: AsyncClient):
        assert (await client.get("/users/1/friends")).status_code == 401

    async def test_add_and_list_friend(self, client: AsyncClient, tokens):
        response = await client.post("/users/1/friends", json={"user_id": 2},
                                     headers=bearer(tokens["a"]))
        assert response.status_code == 200

        response = await client.get("/users/1/friends", headers=bearer(tokens["a"]))
        assert response.status_code == 200
        friends = response.json()
        assert len(friends) == 1
        assert friends[0]["id"] == 2

        # friendship is symmetric
        response = await client.get("/users/2/friends", headers=bearer(tokens["b"]))
        assert [friend["id"] for friend in response.json()] == [1]

    async def test_add_friend_for_someone_else_is_403(self, client: AsyncClient, tokens):
        response = await client.post("/users/2/friends", json={"user_id": 3},
                                     headers=bearer(tokens["a"]))
        assert response.status_code == 403

    async def test_add_self_is_400(self, client: AsyncClient, tokens):
        response = await client.post("/users/1/friends", json={"user_id": 1},
                                     headers=bearer(tokens["a"]))
        assert response.status_code == 400

    async def test_add_unknown_user_is_404(self, client: AsyncClient, tokens):
        response = await client.post("/users/1/friends", json={"user_id": 999},
                                     headers=bearer(tokens["a"]))
        assert response.status_code == 404

    async def test_duplicate_friend_is_400(self, client: AsyncClient, tokens):
        await client.post("/users/1/friends", json={"user_id": 2}, headers=bearer(tokens["a"]))
        response = await client.post("/users/1/friends", json={"user_id": 2},
                                     headers=bearer(tokens["a"]))
        assert response.status_code == 400

    async def test_remove_friend(self, client: AsyncClient, tokens):
        await client.post("/users/1/friends", json={"user_id": 2}, headers=bearer(tokens["a"]))
        response = await client.delete("/users/1/friends/2", headers=bearer(tokens["a"]))
        assert response.status_code == 200
        response = await client.get("/users/1/friends", headers=bearer(tokens["a"]))
        assert response.json() == []

    async def test_remove_missing_friend_is_404(self, client: AsyncClient, tokens):
        response = await client.delete("/users/1/friends/2", headers=bearer(tokens["a"]))
        assert response.status_code == 404


class TestSubscriptions:

    async def test_requires_token(self, client: AsyncClient):
        assert (await client.get("/users/1/subscriptions")).status_code == 401

    async def test_subscribe_to_topic_group(self, client: AsyncClient, tokens, topic_group):
        response = await client.post("/users/1/subscriptions",
                                     json={"group_id": topic_group.id},
                                     headers=bearer(tokens["a"]))
        assert response.status_code == 200

        response = await client.get("/users/1/subscriptions", headers=bearer(tokens["a"]))
        assert response.status_code == 200
        items = response.json()
        assert len(items) == 1
        assert items[0]["sub_type"] == "group"
        assert items[0]["name"] == "209th Brigade"
        assert items[0]["user_id"] == -1

    async def test_subscribe_to_personal_group_maps_to_user(self, client, tokens, container):
        await client.patch("/users/2", json={"name": "Boris", "surname": "Falko"},
                           headers=merge_patch_headers(tokens["b"]))
        user2 = await container.user_repo.get(2)

        response = await client.post("/users/1/subscriptions",
                                     json={"group_id": user2.personal_group_id},
                                     headers=bearer(tokens["a"]))
        assert response.status_code == 200

        items = (await client.get("/users/1/subscriptions", headers=bearer(tokens["a"]))).json()
        assert items[0]["sub_type"] == "user"
        assert items[0]["user_id"] == 2
        assert items[0]["name"] == "Boris Falko"

    async def test_subscribe_unknown_group_is_404(self, client: AsyncClient, tokens):
        response = await client.post("/users/1/subscriptions", json={"group_id": 999},
                                     headers=bearer(tokens["a"]))
        assert response.status_code == 404

    async def test_moderator_flag_by_regular_user_is_403(self, client, tokens, topic_group):
        response = await client.post("/users/1/subscriptions",
                                     json={"group_id": topic_group.id, "is_moderator": True},
                                     headers=bearer(tokens["a"]))
        assert response.status_code == 403

    async def test_admin_grants_moderator_on_topic_group(self, client, tokens, topic_group):
        response = await client.post("/users/1/subscriptions",
                                     json={"group_id": topic_group.id, "is_moderator": True},
                                     headers=bearer(tokens["admin"]))
        assert response.status_code == 200
        items = (await client.get("/users/1/subscriptions", headers=bearer(tokens["a"]))).json()
        assert items[0]["is_moderator"] is True

    async def test_admin_cannot_grant_moderator_on_personal_group(self, client, tokens, container):
        user2 = await container.user_repo.get(2)
        response = await client.post("/users/2/subscriptions",
                                     json={"group_id": user2.personal_group_id,
                                           "is_moderator": True},
                                     headers=bearer(tokens["admin"]))
        assert response.status_code == 403

    async def test_unsubscribe(self, client, tokens, topic_group):
        await client.post("/users/1/subscriptions", json={"group_id": topic_group.id},
                          headers=bearer(tokens["a"]))
        items = (await client.get("/users/1/subscriptions", headers=bearer(tokens["a"]))).json()
        response = await client.delete(f"/users/1/subscriptions/{items[0]['id']}",
                                       headers=bearer(tokens["a"]))
        assert response.status_code == 200
        subscriptions = await client.get("/users/1/subscriptions", headers=bearer(tokens["a"]))
        assert subscriptions.json() == []

    async def test_unsubscribe_missing_is_404(self, client: AsyncClient, tokens):
        response = await client.delete("/users/1/subscriptions/999", headers=bearer(tokens["a"]))
        assert response.status_code == 404
