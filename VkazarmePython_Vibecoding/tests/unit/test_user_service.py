"""UserService unit tests: profile rules, friends, subscriptions."""

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
async def users(container):
    """Creates three users; returns a helper to mint their tokens."""
    sign = container.sign_service
    for email in ("a@t.com", "b@t.com", "c@t.com"):
        await sign.sign_up(dm.SignUpData(email=email, password=USER_PASSWORD))

    def token_for(user_id: int) -> dm.AuthToken:
        return container.auth_service.issue_token(user_id, dm.Role.USER)

    return token_for


@pytest.fixture
async def topic_group(container):
    """A non-personal (admin-created) group for subscription tests."""
    return await container.group_repo.add(dm.Group(id=0, name="209th Brigade"))


class TestProfile:

    async def test_get_user_returns_defaults(self, container, users):
        user = await container.user_service.get_user(1)
        assert user.name == "Noname"
        assert user.surname == "Nosurname"
        assert user.personal_group_id == 1

    async def test_get_unknown_user_raises(self, container, users):
        with pytest.raises(Exception):  # repository UserNotFound
            await container.user_service.get_user(999)

    async def test_patch_applies_only_provided_fields(self, container, users):
        token = users(1)
        updated = await container.user_service.patch_user(
            token, 1, dm.UserPatch(name="Alexander", rang=5)
        )
        assert updated.name == "Alexander"
        assert updated.rang == 5
        assert updated.surname == "Nosurname"  # untouched

    async def test_patch_other_profile_denied(self, container, users):
        with pytest.raises(sex.PermissionDenied):
            await container.user_service.patch_user(users(1), 2, dm.UserPatch(name="Hacked"))

    async def test_delete_requires_admin(self, container, users):
        with pytest.raises(sex.PermissionDenied):
            await container.user_service.delete_user(users(1), 2)

    async def test_admin_delete_cascades_everything(self, container, users):
        admin_token = container.auth_service.issue_token(3, dm.Role.ADMIN)
        # user 1 befriends user 2 and subscribes to a group
        await container.user_service.add_friend(users(1), 1, 2)
        group = await container.group_repo.add(dm.Group(id=0, name="209th Brigade"))
        await container.user_service.subscribe(users(1), 1, dm.Subscription(id=0, user_id=1, group_id=group.id))

        await container.user_service.delete_user(admin_token, 1)

        with pytest.raises(Exception):
            await container.user_repo.get(1)
        with pytest.raises(Exception):
            await container.account_repo.get(1)
        with pytest.raises(Exception):
            await container.group_repo.get(1)  # personal group gone
        assert await container.friend_repo.list_friends(2, dm.UserSearchParams(None, None, 10, 0)) == []
        assert await container.subscription_repo.list_for_user(1, 10, 0) == []


class TestFriends:

    async def test_add_friend_is_symmetric(self, container, users):
        await container.user_service.add_friend(users(1), 1, 2)
        assert await container.friend_repo.exists(1, 2)
        assert await container.friend_repo.exists(2, 1)

    async def test_add_friend_on_someone_elses_list_denied(self, container, users):
        with pytest.raises(sex.PermissionDenied):
            await container.user_service.add_friend(users(1), 2, 3)

    async def test_add_self_as_friend_denied(self, container, users):
        with pytest.raises(sex.SelfFriendship):
            await container.user_service.add_friend(users(1), 1, 1)

    async def test_add_unknown_friend_raises(self, container, users):
        with pytest.raises(Exception):  # repository UserNotFound
            await container.user_service.add_friend(users(1), 1, 999)

    async def test_duplicate_friendship_raises(self, container, users):
        await container.user_service.add_friend(users(1), 1, 2)
        with pytest.raises(Exception):  # repository AlreadyFriends
            await container.user_service.add_friend(users(1), 1, 2)

    async def test_remove_friend(self, container, users):
        await container.user_service.add_friend(users(1), 1, 2)
        await container.user_service.remove_friend(users(1), 1, 2)
        assert not await container.friend_repo.exists(1, 2)

    async def test_remove_missing_friendship_raises(self, container, users):
        with pytest.raises(Exception):  # repository FriendshipNotFound
            await container.user_service.remove_friend(users(1), 1, 2)

    async def test_list_friends_filters_by_name(self, container, users):
        await container.user_service.add_friend(users(1), 1, 2)
        await container.user_service.add_friend(users(1), 1, 3)
        await container.user_service.patch_user(users(2), 2, dm.UserPatch(name="Boris"))

        friends = await container.user_service.list_friends(
            1, dm.UserSearchParams(name="Bor", surname=None, limit=10, offset=0)
        )
        assert [friend.id for friend in friends] == [2]


class TestSubscriptions:

    async def test_subscribe_to_topic_group(self, container, users, topic_group):
        await container.user_service.subscribe(
            users(1), 1, dm.Subscription(id=0, user_id=1, group_id=topic_group.id)
        )
        items = await container.user_service.list_subscriptions(1, limit=10, offset=0)
        assert len(items) == 1
        item = items[0]
        assert item.sub_type == dm.SubType.GROUP
        assert item.group_id == topic_group.id
        assert item.user_id == -1
        assert item.name == "209th Brigade"

    async def test_subscribe_to_personal_group_maps_to_user_type(self, container, users):
        await container.user_service.patch_user(users(2), 2, dm.UserPatch(name="Boris", surname="Falls"))
        user2 = await container.user_repo.get(2)
        await container.user_service.subscribe(
            users(1), 1, dm.Subscription(id=0, user_id=1, group_id=user2.personal_group_id)
        )
        items = await container.user_service.list_subscriptions(1, limit=10, offset=0)
        item = items[0]
        assert item.sub_type == dm.SubType.USER
        assert item.user_id == 2
        assert item.group_id == user2.personal_group_id
        assert item.name == "Boris Falls"

    async def test_subscribe_to_unknown_group_raises(self, container, users):
        with pytest.raises(Exception):  # repository GroupNotFound
            await container.user_service.subscribe(
                users(1), 1, dm.Subscription(id=0, user_id=1, group_id=999)
            )

    async def test_duplicate_subscription_raises(self, container, users, topic_group):
        await container.user_service.subscribe(
            users(1), 1, dm.Subscription(id=0, user_id=1, group_id=topic_group.id)
        )
        with pytest.raises(Exception):  # repository AlreadySubscribed
            await container.user_service.subscribe(
                users(1), 1, dm.Subscription(id=0, user_id=1, group_id=topic_group.id)
            )

    async def test_moderator_flag_requires_admin(self, container, users, topic_group):
        with pytest.raises(sex.PermissionDenied):
            await container.user_service.subscribe(
                users(1), 1,
                dm.Subscription(id=0, user_id=1, group_id=topic_group.id, is_moderator=True),
            )

    async def test_admin_can_grant_moderator_on_topic_group(self, container, users, topic_group):
        admin = container.auth_service.issue_token(1, dm.Role.ADMIN)
        await container.user_service.subscribe(
            admin, 1,
            dm.Subscription(id=0, user_id=1, group_id=topic_group.id, is_moderator=True),
        )
        items = await container.user_service.list_subscriptions(1, limit=10, offset=0)
        assert items[0].is_moderator is True

    async def test_admin_cannot_grant_moderator_on_personal_group(self, container, users):
        admin = container.auth_service.issue_token(1, dm.Role.ADMIN)
        user2 = await container.user_repo.get(2)
        with pytest.raises(sex.PermissionDenied):
            await container.user_service.subscribe(
                admin, 2,
                dm.Subscription(id=0, user_id=2, group_id=user2.personal_group_id, is_moderator=True),
            )

    async def test_admin_can_subscribe_someone_else(self, container, users, topic_group):
        admin = container.auth_service.issue_token(1, dm.Role.ADMIN)
        await container.user_service.subscribe(
            admin, 2, dm.Subscription(id=0, user_id=2, group_id=topic_group.id)
        )
        items = await container.user_service.list_subscriptions(2, limit=10, offset=0)
        assert len(items) == 1

    async def test_user_cannot_subscribe_someone_else(self, container, users, topic_group):
        with pytest.raises(sex.PermissionDenied):
            await container.user_service.subscribe(
                users(1), 2, dm.Subscription(id=0, user_id=2, group_id=topic_group.id)
            )

    async def test_unsubscribe(self, container, users, topic_group):
        await container.user_service.subscribe(
            users(1), 1, dm.Subscription(id=0, user_id=1, group_id=topic_group.id)
        )
        subscription_id = (await container.subscription_repo.list_for_user(1, 10, 0))[0].id
        await container.user_service.unsubscribe(users(1), 1, subscription_id)
        assert await container.subscription_repo.list_for_user(1, 10, 0) == []

    async def test_unsubscribe_missing_raises(self, container, users):
        with pytest.raises(Exception):  # repository SubscriptionNotFound
            await container.user_service.unsubscribe(users(1), 1, 999)

    async def test_unsubscribe_someone_elses_denied(self, container, users, topic_group):
        await container.user_service.subscribe(
            users(1), 1, dm.Subscription(id=0, user_id=1, group_id=topic_group.id)
        )
        subscription_id = (await container.subscription_repo.list_for_user(1, 10, 0))[0].id
        with pytest.raises(sex.PermissionDenied):
            await container.user_service.unsubscribe(users(2), 1, subscription_id)
