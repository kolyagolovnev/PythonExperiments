"""Users, friends and subscriptions.

Permission rules (from the spec):
- PATCH /users/{UserID}          - only the owner of the profile
- DELETE /users/{UserID}         - admin only; cascades account, personal
                                   group, friendships and subscriptions
- friends add/remove             - only on your own list
- subscriptions create/remove    - your own, or an admin's; is_moderator
                                   may only be set by an admin and never
                                   on someone's personal group

Repository exceptions (UserNotFound, GroupNotFound, ...) propagate as-is;
app/main.py maps both repository and service errors onto HTTP codes.
"""

from app.domains import models as dm
from app.repositories.interfaces import (
    AccountRepository,
    FriendRepository,
    GroupRepository,
    SubscriptionRepository,
    UserRepository,
)
from app.services.exceptions import PermissionDenied, SelfFriendship
from app.services.group_service import GroupService
from app.services.chat_service import ChatService


class UserService:
    def __init__(
        self,
        account_repo: AccountRepository,
        user_repo: UserRepository,
        group_repo: GroupRepository,
        friend_repo: FriendRepository,
        subscription_repo: SubscriptionRepository,
        group_service: GroupService,
        chat_service: ChatService,
    ):
        self._account_repo = account_repo
        self._user_repo = user_repo
        self._group_repo = group_repo
        self._friend_repo = friend_repo
        self._subscription_repo = subscription_repo
        self._group_service = group_service
        self._chat_service = chat_service

    # --- profile ---

    async def get_user(self, user_id: int) -> dm.User:
        return await self._user_repo.get(user_id)

    async def search_users(self, params: dm.UserSearchParams) -> list[dm.UserListItem]:
        return await self._user_repo.search(params)

    async def patch_user(self, requester: dm.AuthToken, user_id: int,
                         patch: dm.UserPatch) -> dm.User:
        # existence first: a missing profile is 404, a foreign one is 403
        user = await self._user_repo.get(user_id)
        self._ensure_self(requester, user_id)
        for field_name, value in vars(patch).items():
            if value is not None:
                setattr(user, field_name, value)
        return await self._user_repo.update(user)

    async def delete_user(self, requester: dm.AuthToken, user_id: int) -> None:
        if requester.role != dm.Role.ADMIN:
            raise PermissionDenied()
        user = await self._user_repo.get(user_id)
        await self._friend_repo.remove_all_for_user(user_id)
        await self._subscription_repo.remove_all_for_user(user_id)
        # personal group goes with the user (spec: admins cannot delete or
        # modify a personal group except by deleting the user)
        await self._group_service.delete_group(None, user.personal_group_id)
        # memberships disappear; personal chats of the user are deleted too
        await self._chat_service.remove_user_from_all_chats(user_id)
        await self._user_repo.delete(user_id)
        await self._account_repo.delete(user_id)

    # --- friends ---

    async def list_friends(self, user_id: int,
                           params: dm.UserSearchParams) -> list[dm.FriendListItem]:
        await self._user_repo.get(user_id)
        return await self._friend_repo.list_friends(user_id, params)

    async def add_friend(self, requester: dm.AuthToken, user_id: int,
                         friend_user_id: int) -> None:
        self._ensure_self(requester, user_id)
        if user_id == friend_user_id:
            raise SelfFriendship()
        await self._user_repo.get(user_id)
        await self._user_repo.get(friend_user_id)  # UserNotFound -> 404
        await self._friend_repo.add(user_id, friend_user_id)

    async def remove_friend(self, requester: dm.AuthToken, user_id: int,
                            friend_user_id: int) -> None:
        self._ensure_self(requester, user_id)
        await self._user_repo.get(user_id)
        await self._friend_repo.remove(user_id, friend_user_id)

    # --- subscriptions ---

    async def list_subscriptions(self, user_id: int, limit: int,
                                 offset: int) -> list[dm.SubscriptionListItem]:
        await self._user_repo.get(user_id)
        items: list[dm.SubscriptionListItem] = []
        for subscription in await self._subscription_repo.list_for_user(user_id, limit, offset):
            items.append(await self._to_list_item(subscription))
        return items

    async def subscribe(self, requester: dm.AuthToken, user_id: int,
                        subscription: dm.Subscription) -> None:
        await self._user_repo.get(user_id)
        group = await self._group_repo.get(subscription.group_id)  # GroupNotFound -> 404
        if requester.sub != user_id and requester.role != dm.Role.ADMIN:
            raise PermissionDenied()
        if subscription.is_moderator:
            if requester.role != dm.Role.ADMIN:
                raise PermissionDenied()
            if group.is_personal:
                raise PermissionDenied()
        await self._subscription_repo.add(subscription)

    async def unsubscribe(self, requester: dm.AuthToken, user_id: int,
                          subscription_id: int) -> None:
        await self._user_repo.get(user_id)
        if requester.sub != user_id and requester.role != dm.Role.ADMIN:
            raise PermissionDenied()
        await self._subscription_repo.remove(user_id, subscription_id)

    # --- helpers ---

    @staticmethod
    def _ensure_self(requester: dm.AuthToken, user_id: int) -> None:
        if requester.sub != user_id:
            raise PermissionDenied()

    async def _to_list_item(self, subscription: dm.Subscription) -> dm.SubscriptionListItem:
        group = await self._group_repo.get(subscription.group_id)
        if group.is_personal:
            owner = await self._user_repo.get(group.owner_id)  # type: ignore[arg-type]
            return dm.SubscriptionListItem(
                id=subscription.id,
                sub_type=dm.SubType.USER,
                group_id=group.id,
                user_id=owner.id,
                name=f"{owner.name} {owner.surname}".strip(),
                is_moderator=subscription.is_moderator,
                photo_url=owner.photo_url,
            )
        return dm.SubscriptionListItem(
            id=subscription.id,
            sub_type=dm.SubType.GROUP,
            group_id=group.id,
            user_id=-1,
            name=group.name,
            is_moderator=subscription.is_moderator,
            photo_url=group.photo_url,
        )
