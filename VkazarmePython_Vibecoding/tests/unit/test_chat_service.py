"""ChatService unit tests: creation rules, membership, messages, cascade."""

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
    """Users 1-3 signed up; returns their token factory."""
    for email in ("a@t.com", "b@t.com", "c@t.com"):
        await container.sign_service.sign_up(dm.SignUpData(email=email, password=USER_PASSWORD))

    def token_for(user_id: int) -> dm.AuthToken:
        return container.auth_service.issue_token(user_id, dm.Role.USER)

    return token_for


@pytest.fixture
async def personal_chat(container, env):
    return await container.chat_service.create_chat(
        env(1), name="", chat_type=dm.ChatType.PERSONAL, users=[2], photo_url=""
    )


@pytest.fixture
async def public_chat(container, env):
    return await container.chat_service.create_chat(
        env(1), name="Reunion", chat_type=dm.ChatType.PUBLIC, users=[2], photo_url=""
    )


class TestCreateChat:

    async def test_personal_chat_has_two_members_no_owner(self, container, env, personal_chat):
        assert personal_chat.chat_type == dm.ChatType.PERSONAL
        members = await container.chat_member_repo.user_ids_for_chat(personal_chat.id)
        assert members == [1, 2]
        assert personal_chat.owner_id is None

    async def test_personal_chat_is_idempotent_both_directions(self, container, env, personal_chat):
        again = await container.chat_service.create_chat(
            env(1), name="", chat_type=dm.ChatType.PERSONAL, users=[2], photo_url=""
        )
        from_b = await container.chat_service.create_chat(
            env(2), name="", chat_type=dm.ChatType.PERSONAL, users=[1], photo_url=""
        )
        assert again.id == personal_chat.id
        assert from_b.id == personal_chat.id

    async def test_personal_chat_requires_exactly_one_other(self, container, env):
        with pytest.raises(sex.InvalidChatMembers):  # zero others
            await container.chat_service.create_chat(
                env(1), name="", chat_type=dm.ChatType.PERSONAL, users=[1], photo_url=""
            )
        with pytest.raises(sex.InvalidChatMembers):  # two others
            await container.chat_service.create_chat(
                env(1), name="", chat_type=dm.ChatType.PERSONAL, users=[2, 3], photo_url=""
            )

    async def test_personal_chat_with_unknown_user_is_404(self, container, env):
        with pytest.raises(Exception):  # repository UserNotFound
            await container.chat_service.create_chat(
                env(1), name="", chat_type=dm.ChatType.PERSONAL, users=[999], photo_url=""
            )

    async def test_public_chat_creator_is_owner(self, container, env, public_chat):
        assert public_chat.chat_type == dm.ChatType.PUBLIC
        assert public_chat.owner_id == 1
        assert public_chat.name == "Reunion"
        owner = await container.chat_member_repo.get(public_chat.id, 1)
        assert owner.is_owner is True
        member = await container.chat_member_repo.get(public_chat.id, 2)
        assert member.is_owner is False


class TestListChats:

    async def test_lists_only_own_chats(self, container, env, personal_chat, public_chat):
        items = await container.chat_service.list_chats(env(1), limit=10, offset=0)
        assert [item.id for item in items] == [personal_chat.id, public_chat.id]
        # user 3 is in no chat yet
        assert await container.chat_service.list_chats(env(3), limit=10, offset=0) == []

    async def test_personal_chat_named_after_the_other_participant(
            self, container, env, personal_chat):
        for_a = await container.chat_service.list_chats(env(1), limit=10, offset=0)
        for_b = await container.chat_service.list_chats(env(2), limit=10, offset=0)
        assert for_a[0].name == "Noname Nosurname"  # user 2's default names
        assert for_b[0].name == "Noname Nosurname"  # user 1's default names

    async def test_renamed_participant_changes_personal_chat_name(
            self, container, env, personal_chat):
        from app.domains import models as dm
        await container.user_service.patch_user(env(2), 2, dm.UserPatch(name="Boris", surname="Falko"))
        for_a = await container.chat_service.list_chats(env(1), limit=10, offset=0)
        assert for_a[0].name == "Boris Falko"


class TestGetChat:

    async def test_member_can_read(self, container, env, personal_chat):
        chat = await container.chat_service.get_chat(env(2), personal_chat.id)
        assert chat.id == personal_chat.id

    async def test_stranger_is_403(self, container, env, personal_chat):
        with pytest.raises(sex.PermissionDenied):
            await container.chat_service.get_chat(env(3), personal_chat.id)

    async def test_unknown_chat_is_404(self, container, env):
        with pytest.raises(Exception):  # repository ChatNotFound
            await container.chat_service.get_chat(env(1), 999)


class TestMembers:

    async def test_any_member_adds_to_public_chat(self, container, env, public_chat):
        await container.chat_service.add_member(env(2), public_chat.id, 3)
        member = await container.chat_member_repo.get(public_chat.id, 3)
        assert member.is_owner is False

    async def test_non_member_cannot_add(self, container, env, public_chat):
        with pytest.raises(sex.PermissionDenied):
            await container.chat_service.add_member(env(3), public_chat.id, 3)

    async def test_duplicate_member_is_400(self, container, env, public_chat):
        with pytest.raises(Exception):  # repository AlreadyMember -> HTTP 400
            await container.chat_service.add_member(env(1), public_chat.id, 2)

    async def test_cannot_add_to_personal_chat(self, container, env, personal_chat):
        with pytest.raises(sex.PersonalChatFixed):
            await container.chat_service.add_member(env(1), personal_chat.id, 3)

    async def test_unknown_user_is_404(self, container, env, public_chat):
        with pytest.raises(Exception):  # repository UserNotFound
            await container.chat_service.add_member(env(1), public_chat.id, 999)

    async def test_owner_removes_member(self, container, env, public_chat):
        await container.chat_service.remove_member(env(1), public_chat.id, 2)
        assert not await container.chat_member_repo.is_member(public_chat.id, 2)

    async def test_member_leaves_on_own(self, container, env, public_chat):
        await container.chat_service.remove_member(env(2), public_chat.id, 2)
        assert not await container.chat_member_repo.is_member(public_chat.id, 2)

    async def test_owner_cannot_be_removed(self, container, env, public_chat):
        with pytest.raises(sex.CannotRemoveOwner):
            await container.chat_service.remove_member(env(2), public_chat.id, 1)

    async def test_owner_cannot_leave(self, container, env, public_chat):
        with pytest.raises(sex.CannotRemoveOwner):
            await container.chat_service.remove_member(env(1), public_chat.id, 1)

    async def test_stranger_cannot_remove_others(self, container, env, public_chat):
        # user 3 is not a member and tries to remove user 2
        with pytest.raises(sex.PermissionDenied):
            await container.chat_service.remove_member(env(3), public_chat.id, 2)

    async def test_missing_membership_is_404(self, container, env, public_chat):
        with pytest.raises(Exception):  # repository ChatMemberNotFound
            await container.chat_service.remove_member(env(1), public_chat.id, 3)

    async def test_personal_chat_members_cannot_be_removed(self, container, env, personal_chat):
        with pytest.raises(sex.PersonalChatFixed):
            await container.chat_service.remove_member(env(1), personal_chat.id, 2)


class TestMessages:

    async def test_members_exchange_messages(self, container, env, personal_chat):
        await container.chat_service.send_message(env(1), personal_chat.id, "hello")
        await container.chat_service.send_message(env(2), personal_chat.id, "hi!")
        messages = await container.chat_service.list_messages(
            env(1), personal_chat.id, limit=10, offset=0)
        assert [message.text for message in messages] == ["hello", "hi!"]
        assert messages[0].author_id == 1

    async def test_stranger_cannot_send_or_read(self, container, env, personal_chat):
        with pytest.raises(sex.PermissionDenied):
            await container.chat_service.send_message(env(3), personal_chat.id, "spam")
        with pytest.raises(sex.PermissionDenied):
            await container.chat_service.list_messages(env(3), personal_chat.id, 10, 0)

    async def test_pagination(self, container, env, personal_chat):
        for i in range(3):
            await container.chat_service.send_message(env(1), personal_chat.id, f"m{i}")
        page = await container.chat_service.list_messages(
            env(1), personal_chat.id, limit=2, offset=1)
        assert [message.text for message in page] == ["m1", "m2"]


class TestUserDeletionCascade:

    async def test_deleting_user_removes_personal_chat_and_messages(self, container, env):
        admin = container.auth_service.issue_token(3, dm.Role.ADMIN)
        chat = await container.chat_service.create_chat(
            env(1), name="", chat_type=dm.ChatType.PERSONAL, users=[2], photo_url=""
        )
        await container.chat_service.send_message(env(1), chat.id, "gone soon")
        await container.user_service.delete_user(admin, 2)

        with pytest.raises(Exception):  # repository ChatNotFound
            await container.chat_service.get_chat(env(1), chat.id)
        assert await container.message_repo.list_for_chat(chat.id, 10, 0) == []

    async def test_deleting_user_keeps_public_chat(self, container, env):
        admin = container.auth_service.issue_token(3, dm.Role.ADMIN)
        chat = await container.chat_service.create_chat(
            env(1), name="Reunion", chat_type=dm.ChatType.PUBLIC, users=[2], photo_url=""
        )
        await container.chat_service.send_message(env(2), chat.id, "by me, deleted soon")
        await container.user_service.delete_user(admin, 2)

        still = await container.chat_service.get_chat(env(1), chat.id)
        assert still.id == chat.id
        # the deleted user's message stays but their membership is gone
        assert not await container.chat_member_repo.is_member(chat.id, 2)
        assert len(await container.message_repo.list_for_chat(chat.id, 10, 0)) == 1
