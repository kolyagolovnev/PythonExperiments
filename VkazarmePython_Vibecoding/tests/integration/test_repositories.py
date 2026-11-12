"""Behavioral parity tests: the SQLAlchemy repositories must behave exactly
like the in-memory ones. Every test runs against SQLite and (when Docker is
available) against a real PostgreSQL container — see conftest.py."""

import pytest
from app.domains import models as dm

from app.services import exceptions as sex


class TestAccounts:

    async def test_signup_creates_account_user_and_personal_group(self, db_container):
        await db_container.sign_service.sign_up(
            dm.SignUpData(email="x@t.com", password="Password123"))
        account = await db_container.account_repo.find_by_email("x@t.com")
        assert account is not None
        user = await db_container.user_repo.get(account.id)
        group = await db_container.group_repo.get(user.personal_group_id)
        assert group.is_personal and group.owner_id == account.id

    async def test_duplicate_email_case_insensitive(self, db_container):
        await db_container.sign_service.sign_up(
            dm.SignUpData(email="x@t.com", password="Password123"))
        with pytest.raises(sex.EmailIsBusy):
            await db_container.sign_service.sign_up(
                dm.SignUpData(email="X@T.COM", password="Password123"))

    async def test_signin_wrong_password(self, db_container):
        await db_container.sign_service.sign_up(
            dm.SignUpData(email="x@t.com", password="Password123"))
        with pytest.raises(sex.IncorrectEmailOrPassword):
            await db_container.sign_service.sign_in(
                dm.SignInRequest(email="x@t.com", password="WrongPass1"))

    async def test_email_lookup_is_case_insensitive(self, db_container):
        await db_container.sign_service.sign_up(
            dm.SignUpData(email="MiXeD@t.com", password="Password123"))
        assert await db_container.account_repo.find_by_email("mixed@T.COM") is not None


class TestProfiles:

    async def test_patch_and_search(self, db_container, db_users):
        await db_container.user_service.patch_user(
            db_users(2), 2, dm.UserPatch(name="Boris", surname="Falko", rang=5))
        user = await db_container.user_repo.get(2)
        assert (user.name, user.surname, user.rang) == ("Boris", "Falko", 5)

        found = await db_container.user_service.search_users(
            dm.UserSearchParams(name="bor", surname=None, limit=10, offset=0))
        assert [item.id for item in found] == [2]

        page = await db_container.user_service.search_users(
            dm.UserSearchParams(name=None, surname=None, limit=2, offset=1))
        assert [item.id for item in page] == [2, 3]

    async def test_patch_only_provided_fields(self, db_container, db_users):
        await db_container.user_service.patch_user(
            db_users(1), 1, dm.UserPatch(name="Alexander"))
        user = await db_container.user_repo.get(1)
        assert user.name == "Alexander" and user.surname == "Nosurname"


class TestFriends:

    async def test_symmetric_add_remove_and_duplicates(self, db_container, db_users):
        await db_container.user_service.add_friend(db_users(1), 1, 2)
        assert await db_container.friend_repo.exists(1, 2)
        assert await db_container.friend_repo.exists(2, 1)

        friends = await db_container.friend_repo.list_friends(
            2, dm.UserSearchParams(None, None, 10, 0))
        assert [friend.id for friend in friends] == [1]

        with pytest.raises(Exception):  # repository AlreadyFriends
            await db_container.user_service.add_friend(db_users(1), 1, 2)

        await db_container.user_service.remove_friend(db_users(1), 1, 2)
        assert not await db_container.friend_repo.exists(1, 2)
        with pytest.raises(Exception):  # repository FriendshipNotFound
            await db_container.user_service.remove_friend(db_users(1), 1, 2)

    async def test_remove_all_for_user_cleans_both_directions(self, db_container, db_users):
        await db_container.user_service.add_friend(db_users(1), 1, 2)
        await db_container.user_service.add_friend(db_users(1), 1, 3)
        await db_container.friend_repo.remove_all_for_user(1)
        assert not await db_container.friend_repo.exists(2, 1)
        assert not await db_container.friend_repo.exists(3, 1)


class TestSubscriptions:

    async def test_subscribe_unsubscribe_and_duplicate(self, db_container, db_users):
        topic = await db_container.group_repo.add(dm.Group(id=0, name="209th Brigade"))
        await db_container.user_service.subscribe(
            db_users(1), 1, dm.Subscription(id=0, user_id=1, group_id=topic.id))
        with pytest.raises(Exception):  # repository AlreadySubscribed
            await db_container.user_service.subscribe(
                db_users(1), 1, dm.Subscription(id=0, user_id=1, group_id=topic.id))

        items = await db_container.user_service.list_subscriptions(1, limit=10, offset=0)
        assert items[0].sub_type == dm.SubType.GROUP

        await db_container.user_service.unsubscribe(db_users(1), 1, items[0].id)
        assert await db_container.subscription_repo.list_for_user(1, 10, 0) == []

    async def test_personal_group_subscription_maps_to_user(self, db_container, db_users):
        await db_container.user_service.patch_user(
            db_users(2), 2, dm.UserPatch(name="Boris", surname="Falko"))
        user2 = await db_container.user_repo.get(2)
        await db_container.user_service.subscribe(
            db_users(1), 1,
            dm.Subscription(id=0, user_id=1, group_id=user2.personal_group_id))
        items = await db_container.user_service.list_subscriptions(1, limit=10, offset=0)
        assert items[0].sub_type == dm.SubType.USER
        assert items[0].user_id == 2 and items[0].name == "Boris Falko"


class TestGroupsAndPastes:

    async def test_group_search_lists_topic_groups_only(self, db_container, db_users):
        admin = db_users(1, dm.Role.ADMIN)
        topic = await db_container.group_service.create_group(
            admin, dm.GroupPost(name="209th Brigade"))
        found = await db_container.group_service.search_groups("brigade", limit=10, offset=0)
        assert [group.id for group in found] == [topic.id]

    async def test_group_delete_cascades(self, db_container, db_users):
        admin = db_users(1, dm.Role.ADMIN)
        topic = await db_container.group_service.create_group(
            admin, dm.GroupPost(name="209th Brigade"))
        await db_container.user_service.subscribe(
            db_users(2), 2, dm.Subscription(id=0, user_id=2, group_id=topic.id))
        await db_container.paste_service.create_paste(admin, topic.id, "hello")
        paste = (await db_container.paste_repo.list_for_group(topic.id, 10, 0))[0]
        await db_container.paste_service.add_comment(db_users(2), topic.id, paste.id, "hi")

        await db_container.group_service.delete_group(admin, topic.id)

        with pytest.raises(Exception):
            await db_container.group_repo.get(topic.id)
        assert await db_container.paste_repo.list_for_group(topic.id, 10, 0) == []
        assert await db_container.comment_repo.list_for_paste(paste.id, 10, 0) == []
        assert await db_container.subscription_repo.find_for_user_group(2, topic.id) is None

    async def test_posting_rules_and_comments(self, db_container, db_users):
        admin = db_users(1, dm.Role.ADMIN)
        # personal group: owner only
        await db_container.paste_service.create_paste(db_users(1), 1, "mine")
        with pytest.raises(sex.PermissionDenied):
            await db_container.paste_service.create_paste(db_users(2), 1, "spam")

        paste = await db_container.paste_service.create_paste(db_users(1), 1, "mine again")
        comment = await db_container.paste_service.add_comment(
            db_users(2), 1, paste.id, "be strong")
        assert comment.author.id == 2

        # deleting the paste drops its comments
        await db_container.paste_service.delete_paste(db_users(1), 1, paste.id)
        assert await db_container.comment_repo.list_for_paste(paste.id, 10, 0) == []


class TestChats:

    async def test_personal_chat_idempotent_and_named_after_other(self, db_container, db_users):
        chat = await db_container.chat_service.create_chat(
            db_users(1), name="", chat_type=dm.ChatType.PERSONAL, users=[2], photo_url="")
        again = await db_container.chat_service.create_chat(
            db_users(2), name="", chat_type=dm.ChatType.PERSONAL, users=[1], photo_url="")
        assert again.id == chat.id

        await db_container.user_service.patch_user(
            db_users(2), 2, dm.UserPatch(name="Boris", surname="Falko"))
        items = await db_container.chat_service.list_chats(db_users(1), limit=10, offset=0)
        assert items[0].name == "Boris Falko"

    async def test_messages_and_membership(self, db_container, db_users):
        chat = await db_container.chat_service.create_chat(
            db_users(1), name="Reunion", chat_type=dm.ChatType.PUBLIC,
            users=[2], photo_url="")
        await db_container.chat_service.send_message(db_users(1), chat.id, "hello")
        await db_container.chat_service.send_message(db_users(2), chat.id, "hi")
        messages = await db_container.chat_service.list_messages(
            db_users(1), chat.id, limit=10, offset=0)
        assert [message.text for message in messages] == ["hello", "hi"]

        with pytest.raises(sex.PermissionDenied):
            await db_container.chat_service.send_message(db_users(3), chat.id, "spam")
        with pytest.raises(Exception):  # repository AlreadyMember
            await db_container.chat_service.add_member(db_users(1), chat.id, 2)

    async def test_user_deletion_cascades_everything(self, db_container, db_users):
        admin = db_users(3, dm.Role.ADMIN)
        chat = await db_container.chat_service.create_chat(
            db_users(1), name="", chat_type=dm.ChatType.PERSONAL, users=[2], photo_url="")
        await db_container.chat_service.send_message(db_users(1), chat.id, "gone")
        await db_container.user_service.add_friend(db_users(1), 1, 2)

        await db_container.user_service.delete_user(admin, 1)

        with pytest.raises(Exception):
            await db_container.user_repo.get(1)
        with pytest.raises(Exception):
            await db_container.account_repo.get(1)
        with pytest.raises(Exception):
            await db_container.group_repo.get(1)          # personal group
        with pytest.raises(Exception):
            await db_container.chat_repo.get(chat.id)     # personal chat
        assert await db_container.message_repo.list_for_chat(chat.id, 10, 0) == []
        assert not await db_container.friend_repo.exists(2, 1)


class TestMedia:

    async def test_roundtrip_and_404(self, db_container):
        payload = b"\x89PNG\r\n\x1a\n" + b"0" * 50
        url = await db_container.media_service.save("avatar.png", "image/png", payload)
        media = await db_container.media_service.get(int(url.rsplit("/", 1)[-1]))
        assert media.data == payload and media.content_type == "image/png"

        with pytest.raises(Exception):  # repository MediaNotFound
            await db_container.media_service.get(999)

    async def test_oversize_rejected(self, db_container):
        # db_container fixture lowers media_max_bytes to 100
        with pytest.raises(Exception):
            await db_container.media_service.save("big.png", "image/png", b"x" * 101)
