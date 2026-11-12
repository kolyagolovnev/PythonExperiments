"""End-to-end tests for /groups: groups, pastes (posts), comments.

Covers the spec's status codes: 401 without a token, 403 for non-admin
group management / posting without rights, 404 for missing entities.
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
    return {
        "a": await sign_up_and_sign_in(client, "a@t.com"),          # user 1
        "b": await sign_up_and_sign_in(client, "b@t.com"),          # user 2
        "c": await sign_up_and_sign_in(client, "c@t.com"),          # user 3
        "admin": await sign_up_and_sign_in(client, ADMIN_EMAIL),    # user 4
    }


@pytest.fixture
async def topic_group(client: AsyncClient, tokens) -> int:
    response = await client.post("/groups",
                                 json={"name": "209th Brigade", "description": "railway"},
                                 headers=bearer(tokens["admin"]))
    assert response.status_code == 200
    # group ids: personal groups 1-4, then the topic group is id 5
    return 5


@pytest.fixture
async def moderator(client: AsyncClient, tokens, topic_group):
    """User 2 becomes a moderator of the topic group; user 3 a plain subscriber."""
    response = await client.post("/users/2/subscriptions",
                                 json={"group_id": topic_group, "is_moderator": True},
                                 headers=bearer(tokens["admin"]))
    assert response.status_code == 200
    response = await client.post("/users/3/subscriptions",
                                 json={"group_id": topic_group},
                                 headers=bearer(tokens["c"]))
    assert response.status_code == 200


@pytest.fixture
async def personal_paste(client: AsyncClient, tokens) -> dict:
    """User 1 posts to their own personal group (group 1)."""
    response = await client.post("/groups/1/pastes", json={"text": "I was very sad today"},
                                 headers=bearer(tokens["a"]))
    assert response.status_code == 200
    return {"group_id": 1, "paste_id": 1}


class TestGroupsAuth:

    async def test_requires_token(self, client: AsyncClient):
        assert (await client.get("/groups")).status_code == 401
        assert (await client.get("/groups/1")).status_code == 401
        assert (await client.get("/groups/1/pastes")).status_code == 401
        assert (await client.get("/groups/1/pastes/1/comments")).status_code == 401


class TestGroupCrud:

    async def test_admin_creates_group(self, client: AsyncClient, tokens, topic_group):
        response = await client.get(f"/groups/{topic_group}", headers=bearer(tokens["a"]))
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "209th Brigade"
        assert body["description"] == "railway"

    async def test_regular_user_cannot_create(self, client: AsyncClient, tokens):
        response = await client.post("/groups", json={"name": "Rogue"}, headers=bearer(tokens["a"]))
        assert response.status_code == 403

    async def test_search_lists_topic_groups_only(self, client: AsyncClient, tokens, topic_group):
        response = await client.get("/groups", headers=bearer(tokens["a"]))
        assert response.status_code == 200
        groups = response.json()
        assert [group["id"] for group in groups] == [topic_group]

    async def test_search_filters_by_name(self, client: AsyncClient, tokens, topic_group):
        response = await client.get("/groups", params={"name": "brigade"},
                                    headers=bearer(tokens["a"]))
        assert [group["id"] for group in response.json()] == [topic_group]

        response = await client.get("/groups", params={"name": "fleet"},
                                    headers=bearer(tokens["a"]))
        assert response.json() == []

    async def test_patch_by_regular_user_is_403(self, client: AsyncClient, tokens, topic_group):
        response = await client.patch(f"/groups/{topic_group}", json={"name": "Hacked"},
                                      headers=merge_patch_headers(tokens["a"]))
        assert response.status_code == 403

    async def test_patch_by_moderator_is_403(self, client: AsyncClient, tokens,
                                             topic_group, moderator):
        response = await client.patch(f"/groups/{topic_group}", json={"name": "Hacked"},
                                      headers=merge_patch_headers(tokens["b"]))
        assert response.status_code == 403

    async def test_admin_patches_group(self, client: AsyncClient, tokens, topic_group):
        response = await client.patch(f"/groups/{topic_group}",
                                      json={"description": "railway troops"},
                                      headers=merge_patch_headers(tokens["admin"]))
        assert response.status_code == 200
        body = (await client.get(f"/groups/{topic_group}", headers=bearer(tokens["a"]))).json()
        assert body["description"] == "railway troops"
        assert body["name"] == "209th Brigade"  # untouched

    async def test_patch_unknown_group_is_404(self, client: AsyncClient, tokens):
        response = await client.patch("/groups/999", json={"name": "X"},
                                      headers=merge_patch_headers(tokens["admin"]))
        assert response.status_code == 404

    async def test_admin_deletes_group(self, client: AsyncClient, tokens, topic_group):
        response = await client.delete(f"/groups/{topic_group}", headers=bearer(tokens["admin"]))
        assert response.status_code == 200
        assert (await client.get(f"/groups/{topic_group}",
                                 headers=bearer(tokens["a"]))).status_code == 404

    async def test_regular_user_cannot_delete(self, client: AsyncClient, tokens, topic_group):
        response = await client.delete(f"/groups/{topic_group}", headers=bearer(tokens["a"]))
        assert response.status_code == 403

    async def test_unknown_group_is_404(self, client: AsyncClient, tokens):
        response = await client.get("/groups/999", headers=bearer(tokens["a"]))
        assert response.status_code == 404


class TestPastes:

    async def test_owner_posts_to_personal_group(self, client: AsyncClient, tokens,
                                                 personal_paste):
        response = await client.get(f"/groups/{personal_paste['group_id']}/pastes",
                                    headers=bearer(tokens["a"]))
        pastes = response.json()
        assert len(pastes) == 1
        assert pastes[0]["text"] == "I was very sad today"
        assert pastes[0]["group_id"] == 1
        assert "time" in pastes[0]

    async def test_stranger_cannot_post_to_personal_group(self, client: AsyncClient, tokens):
        response = await client.post("/groups/1/pastes", json={"text": "spam"},
                                     headers=bearer(tokens["b"]))
        assert response.status_code == 403

    async def test_subscriber_cannot_post_to_topic_group(self, client: AsyncClient, tokens,
                                                         topic_group, moderator):
        response = await client.post(f"/groups/{topic_group}/pastes",
                                     json={"text": "just a subscriber"},
                                     headers=bearer(tokens["c"]))
        assert response.status_code == 403

    async def test_moderator_posts_to_topic_group(self, client: AsyncClient, tokens,
                                                  topic_group, moderator):
        response = await client.post(f"/groups/{topic_group}/pastes",
                                     json={"text": "from the moderator"},
                                     headers=bearer(tokens["b"]))
        assert response.status_code == 200

    async def test_get_paste(self, client: AsyncClient, tokens, personal_paste):
        response = await client.get(
            f"/groups/{personal_paste['group_id']}/pastes/{personal_paste['paste_id']}",
            headers=bearer(tokens["b"]))
        assert response.status_code == 200
        assert response.json()["text"] == "I was very sad today"

    async def test_paste_of_another_group_is_404(self, client: AsyncClient, tokens,
                                                 personal_paste, topic_group):
        response = await client.get(
            f"/groups/{topic_group}/pastes/{personal_paste['paste_id']}",
            headers=bearer(tokens["a"]))
        assert response.status_code == 404

    async def test_unknown_paste_is_404(self, client: AsyncClient, tokens):
        response = await client.get("/groups/1/pastes/999", headers=bearer(tokens["a"]))
        assert response.status_code == 404

    async def test_owner_deletes_own_paste(self, client: AsyncClient, tokens, personal_paste):
        response = await client.delete(
            f"/groups/{personal_paste['group_id']}/pastes/{personal_paste['paste_id']}",
            headers=bearer(tokens["a"]))
        assert response.status_code == 200
        response = await client.get("/groups/1/pastes", headers=bearer(tokens["a"]))
        assert response.json() == []

    async def test_stranger_cannot_delete_paste(self, client: AsyncClient, tokens,
                                                personal_paste):
        response = await client.delete(
            f"/groups/{personal_paste['group_id']}/pastes/{personal_paste['paste_id']}",
            headers=bearer(tokens["b"]))
        assert response.status_code == 403

    async def test_moderator_deletes_topic_paste(self, client: AsyncClient, tokens,
                                                 topic_group, moderator):
        await client.post(f"/groups/{topic_group}/pastes", json={"text": "announcement"},
                          headers=bearer(tokens["admin"]))
        pastes = (await client.get(f"/groups/{topic_group}/pastes",
                                   headers=bearer(tokens["b"]))).json()
        paste_id = pastes[0]["id"]
        response = await client.delete(f"/groups/{topic_group}/pastes/{paste_id}",
                                       headers=bearer(tokens["b"]))
        assert response.status_code == 200

    async def test_group_deletion_drops_pastes(self, client: AsyncClient, tokens,
                                               topic_group, moderator):
        await client.post(f"/groups/{topic_group}/pastes", json={"text": "announcement"},
                          headers=bearer(tokens["admin"]))
        await client.delete(f"/groups/{topic_group}", headers=bearer(tokens["admin"]))
        response = await client.get(f"/groups/{topic_group}/pastes", headers=bearer(tokens["a"]))
        assert response.status_code == 404  # the group itself is gone


class TestComments:

    async def test_user_comments_on_paste(self, client: AsyncClient, tokens, personal_paste):
        response = await client.post(
            f"/groups/{personal_paste['group_id']}/pastes/{personal_paste['paste_id']}/comments",
            json={"text": "Keep in touch, brother!"},
            headers=bearer(tokens["b"]))
        assert response.status_code == 200

        response = await client.get(
            f"/groups/{personal_paste['group_id']}/pastes/{personal_paste['paste_id']}/comments",
            headers=bearer(tokens["a"]))
        assert response.status_code == 200
        comments = response.json()
        assert len(comments) == 1
        assert comments[0]["text"] == "Keep in touch, brother!"
        assert comments[0]["paste_id"] == personal_paste["paste_id"]
        assert comments[0]["author"]["id"] == 2

    async def test_comment_on_unknown_paste_is_404(self, client: AsyncClient, tokens):
        response = await client.post("/groups/1/pastes/999/comments",
                                     json={"text": "hi"}, headers=bearer(tokens["a"]))
        assert response.status_code == 404

    async def test_paste_deletion_drops_comments(self, client: AsyncClient, tokens,
                                                 personal_paste):
        await client.post(
            f"/groups/{personal_paste['group_id']}/pastes/{personal_paste['paste_id']}/comments",
            json={"text": "hi"}, headers=bearer(tokens["b"]))
        await client.delete(
            f"/groups/{personal_paste['group_id']}/pastes/{personal_paste['paste_id']}",
            headers=bearer(tokens["a"]))
        # paste gone -> commenting again is 404, not orphaned comments
        response = await client.post(
            f"/groups/{personal_paste['group_id']}/pastes/{personal_paste['paste_id']}/comments",
            json={"text": "hi"}, headers=bearer(tokens["b"]))
        assert response.status_code == 404

    async def test_user_deletion_removes_personal_group_feed(self, client: AsyncClient,
                                                             tokens, personal_paste):
        response = await client.delete("/users/1", headers=bearer(tokens["admin"]))
        assert response.status_code == 200
        response = await client.get("/groups/1", headers=bearer(tokens["admin"]))
        assert response.status_code == 404  # personal group deleted with the user
