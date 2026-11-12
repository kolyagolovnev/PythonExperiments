"""GroupService unit tests: admin CRUD rules, search, deletion cascade."""

import pytest

from app.container import build_container
from app.domains import models as dm
from app.services import exceptions as sex
from app.settings import Settings
from tests.conftest import TEST_SECRET, USER_PASSWORD


@pytest.fixture
def container():
    return build_container(Settings(secret=TEST_SECRET))


@pytest.fixture
async def tokens(container):
    """Three signed-up users; returns a token factory (admins must be minted manually)."""
    for email in ("a@t.com", "b@t.com", "c@t.com"):
        await container.sign_service.sign_up(dm.SignUpData(email=email, password=USER_PASSWORD))

    def token_for(user_id: int, role: dm.Role = dm.Role.USER) -> dm.AuthToken:
        return container.auth_service.issue_token(user_id, role)

    return token_for


@pytest.fixture
async def topic_group(container, tokens):
    admin = tokens(1, dm.Role.ADMIN)
    return await container.group_service.create_group(
        admin, dm.GroupPost(name="209th Brigade", description="railway")
    )


class TestCreateGroup:

    async def test_admin_creates_topic_group(self, container, tokens):
        admin = tokens(1, dm.Role.ADMIN)
        group = await container.group_service.create_group(
            admin, dm.GroupPost(name="209th Brigade", description="railway")
        )
        assert group.owner_id is None  # topic group, not personal
        assert group.name == "209th Brigade"

    async def test_regular_user_denied(self, container, tokens):
        with pytest.raises(sex.PermissionDenied):
            await container.group_service.create_group(tokens(1), dm.GroupPost(name="X"))

    async def test_group_ids_do_not_collide_with_personal_groups(self, container, tokens):
        admin = tokens(1, dm.Role.ADMIN)
        group = await container.group_service.create_group(admin, dm.GroupPost(name="G"))
        user1 = await container.user_repo.get(1)
        assert group.id != user1.personal_group_id


class TestSearchGroups:

    async def test_search_lists_only_topic_groups(self, container, tokens, topic_group):
        # personal groups of users 1-3 must not appear
        results = await container.group_service.search_groups(None, limit=10, offset=0)
        assert [group.id for group in results] == [topic_group.id]

    async def test_search_filters_by_name_case_insensitive(self, container, tokens, topic_group):
        results = await container.group_service.search_groups("brigade", limit=10, offset=0)
        assert [group.id for group in results] == [topic_group.id]

        results = await container.group_service.search_groups("nomatch", limit=10, offset=0)
        assert results == []


class TestPatchGroup:

    async def test_admin_patches_only_provided_fields(self, container, tokens, topic_group):
        admin = tokens(1, dm.Role.ADMIN)
        updated = await container.group_service.patch_group(
            admin, topic_group.id, dm.GroupPatch(description="new description")
        )
        assert updated.description == "new description"
        assert updated.name == "209th Brigade"  # untouched

    async def test_moderator_cannot_patch(self, container, tokens, topic_group):
        # even a moderator of the group is denied (spec is explicit)
        admin = tokens(1, dm.Role.ADMIN)
        moderator = tokens(2)
        await container.user_service.subscribe(
            admin, 2,  # only an admin can grant the moderator flag
            dm.Subscription(id=0, user_id=2, group_id=topic_group.id, is_moderator=True),
        )
        with pytest.raises(sex.PermissionDenied):
            await container.group_service.patch_group(
                moderator, topic_group.id, dm.GroupPatch(name="Hacked")
            )

    async def test_regular_user_cannot_patch(self, container, tokens, topic_group):
        with pytest.raises(sex.PermissionDenied):
            await container.group_service.patch_group(
                tokens(1), topic_group.id, dm.GroupPatch(name="Hacked")
            )


class TestDeleteGroup:

    async def test_admin_deletes_group_with_cascade(self, container, tokens, topic_group):
        admin = tokens(1, dm.Role.ADMIN)
        moderator = tokens(2)
        await container.user_service.subscribe(
            admin, 2,  # only an admin can grant the moderator flag
            dm.Subscription(id=0, user_id=2, group_id=topic_group.id, is_moderator=True),
        )
        await container.paste_service.create_paste(
            moderator, topic_group.id, "hello brigade"
        )
        paste = (await container.paste_repo.list_for_group(topic_group.id, 10, 0))[0]
        await container.paste_service.add_comment(admin, topic_group.id, paste.id, "hi")

        await container.group_service.delete_group(admin, topic_group.id)

        with pytest.raises(Exception):
            await container.group_repo.get(topic_group.id)
        assert await container.paste_repo.list_for_group(topic_group.id, 10, 0) == []
        assert await container.comment_repo.list_for_paste(paste.id, 10, 0) == []
        assert await container.subscription_repo.find_for_user_group(2, topic_group.id) is None

    async def test_regular_user_cannot_delete(self, container, tokens, topic_group):
        with pytest.raises(sex.PermissionDenied):
            await container.group_service.delete_group(tokens(1), topic_group.id)

    async def test_unknown_group_raises(self, container, tokens):
        admin = tokens(1, dm.Role.ADMIN)
        with pytest.raises(Exception):  # repository GroupNotFound
            await container.group_service.delete_group(admin, 999)
