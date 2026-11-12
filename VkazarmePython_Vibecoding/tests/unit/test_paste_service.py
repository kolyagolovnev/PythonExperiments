"""PasteService unit tests: posting and deletion rules, comments."""

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
async def env(container):
    """Users 1-3 signed up; user 1 acts as admin; a topic group with user 2
    as its moderator; user 1 owns personal group 1."""
    for email in ("a@t.com", "b@t.com", "c@t.com"):
        await container.sign_service.sign_up(dm.SignUpData(email=email, password=USER_PASSWORD))

    def token_for(user_id: int, role: dm.Role = dm.Role.USER) -> dm.AuthToken:
        return container.auth_service.issue_token(user_id, role)

    admin = token_for(1, dm.Role.ADMIN)
    topic = await container.group_service.create_group(admin, dm.GroupPost(name="209th Brigade"))
    await container.user_service.subscribe(
        admin, 2,  # only an admin can grant the moderator flag
        dm.Subscription(id=0, user_id=2, group_id=topic.id, is_moderator=True)
    )
    await container.user_service.subscribe(
        token_for(3), 3, dm.Subscription(id=0, user_id=3, group_id=topic.id)
    )
    return {"token": token_for, "admin": admin, "topic": topic}


class TestPostingRules:

    async def test_owner_posts_to_own_personal_group(self, container, env):
        paste = await container.paste_service.create_paste(env["token"](1), 1, "sad today")
        assert paste.group_id == 1
        assert paste.author_id == 1
        assert paste.id > 0 and paste.time is not None

    async def test_stranger_cannot_post_to_personal_group(self, container, env):
        with pytest.raises(sex.PermissionDenied):
            await container.paste_service.create_paste(env["token"](2), 1, "spam")

    async def test_admin_posts_to_topic_group(self, container, env):
        paste = await container.paste_service.create_paste(
            env["admin"], env["topic"].id, "announcement")
        assert paste.group_id == env["topic"].id

    async def test_moderator_posts_to_topic_group(self, container, env):
        paste = await container.paste_service.create_paste(
            env["token"](2), env["topic"].id, "from the moderator")
        assert paste.group_id == env["topic"].id

    async def test_plain_subscriber_cannot_post_to_topic_group(self, container, env):
        with pytest.raises(sex.PermissionDenied):
            await container.paste_service.create_paste(
                env["token"](3), env["topic"].id, "just a subscriber")

    async def test_user_without_subscription_cannot_post(self, container, env):
        # user 2 is a moderator of the topic group but has no link to group 1
        with pytest.raises(sex.PermissionDenied):
            await container.paste_service.create_paste(
                env["token"](2), 1, "spam into someone's profile")


class TestReadingPastes:

    async def test_get_paste_from_wrong_group_is_404(self, container, env):
        paste = await container.paste_service.create_paste(env["token"](1), 1, "mine")
        with pytest.raises(Exception):  # PasteNotFound
            await container.paste_service.get_paste(env["topic"].id, paste.id)

    async def test_unknown_paste_is_404(self, container, env):
        with pytest.raises(Exception):  # PasteNotFound
            await container.paste_service.get_paste(1, 999)

    async def test_list_pastes_paginates(self, container, env):
        for i in range(3):
            await container.paste_service.create_paste(env["token"](1), 1, f"post {i}")
        page = await container.paste_service.list_pastes(1, limit=2, offset=1)
        assert [paste.text for paste in page] == ["post 1", "post 2"]


class TestDeletingPastes:

    async def test_admin_deletes_any_paste(self, container, env):
        paste = await container.paste_service.create_paste(env["token"](1), 1, "mine")
        await container.paste_service.delete_paste(env["admin"], 1, paste.id)
        with pytest.raises(Exception):
            await container.paste_repo.get(paste.id)

    async def test_owner_deletes_paste_in_own_personal_group(self, container, env):
        paste = await container.paste_service.create_paste(env["token"](1), 1, "mine")
        await container.paste_service.delete_paste(env["token"](1), 1, paste.id)

    async def test_moderator_deletes_paste_in_topic_group(self, container, env):
        admin_paste = await container.paste_service.create_paste(
            env["admin"], env["topic"].id, "announcement")
        await container.paste_service.delete_paste(
            env["token"](2), env["topic"].id, admin_paste.id)

    async def test_stranger_cannot_delete(self, container, env):
        paste = await container.paste_service.create_paste(env["token"](1), 1, "mine")
        with pytest.raises(sex.PermissionDenied):
            await container.paste_service.delete_paste(env["token"](2), 1, paste.id)

    async def test_deleting_paste_drops_its_comments(self, container, env):
        paste = await container.paste_service.create_paste(env["token"](1), 1, "mine")
        await container.paste_service.add_comment(env["token"](2), 1, paste.id, "hi")
        await container.paste_service.delete_paste(env["token"](1), 1, paste.id)
        assert await container.comment_repo.list_for_paste(paste.id, 10, 0) == []


class TestComments:

    async def test_any_user_can_comment(self, container, env):
        paste = await container.paste_service.create_paste(env["token"](1), 1, "mine")
        item = await container.paste_service.add_comment(env["token"](3), 1, paste.id, "be strong!")
        assert item.paste_id == paste.id
        assert item.author.id == 3

    async def test_comment_carries_author_projection(self, container, env):
        paste = await container.paste_service.create_paste(env["token"](1), 1, "mine")
        item = await container.paste_service.add_comment(env["token"](2), 1, paste.id, "+")
        assert item.author.personal_group_id == 2
        assert item.author.name == "Noname"

    async def test_list_comments_paginates(self, container, env):
        paste = await container.paste_service.create_paste(env["token"](1), 1, "mine")
        for i in range(3):
            await container.paste_service.add_comment(env["token"](2), 1, paste.id, f"c{i}")
        page = await container.paste_service.list_comments(1, paste.id, limit=2, offset=0)
        assert [comment.text for comment in page] == ["c0", "c1"]

    async def test_comment_on_unknown_paste_is_404(self, container, env):
        with pytest.raises(Exception):  # PasteNotFound
            await container.paste_service.add_comment(env["token"](2), 1, 999, "hi")

    async def test_user_deletion_removes_their_pastes_via_group_cascade(self, container, env):
        # admin deletes user 1 -> personal group 1 and its pastes disappear
        paste = await container.paste_service.create_paste(env["token"](1), 1, "mine")
        await container.user_service.delete_user(env["admin"], 1)
        with pytest.raises(Exception):
            await container.paste_repo.get(paste.id)
