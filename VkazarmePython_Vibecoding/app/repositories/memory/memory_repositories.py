"""In-memory repository implementations.

These act as the mock data layer while the server layer is built out;
the SQLAlchemy/PostgreSQL implementation will replace them behind the
same interfaces in a later milestone.
"""

from dataclasses import replace

from app.domains import models as dm
from app.repositories import exceptions as rex
from app.repositories.interfaces import (
    AccountRepository,
    ChatMemberRepository,
    ChatRepository,
    CommentRepository,
    FriendRepository,
    GroupRepository,
    MediaRepository,
    MessageRepository,
    PasteRepository,
    SubscriptionRepository,
    UserRepository,
)


class InMemoryAccountRepository(AccountRepository):
    def __init__(self) -> None:
        self._by_id: dict[int, dm.Account] = {}
        self._next_id = 1

    async def add(self, account: dm.Account) -> dm.Account:
        email = account.email.lower()
        if any(existing.email.lower() == email for existing in self._by_id.values()):
            raise rex.EmailAlreadyExists()
        stored = replace(account, id=self._next_id)
        self._by_id[stored.id] = stored
        self._next_id += 1
        return stored

    async def find_by_email(self, email: str) -> dm.Account | None:
        for account in self._by_id.values():
            if account.email.lower() == email.lower():
                return account
        return None

    async def get(self, account_id: int) -> dm.Account:
        try:
            return self._by_id[account_id]
        except KeyError:
            raise rex.AccountNotFound()

    async def delete(self, account_id: int) -> None:
        if account_id not in self._by_id:
            raise rex.AccountNotFound()
        del self._by_id[account_id]


class InMemoryUserRepository(UserRepository):
    def __init__(self) -> None:
        self._by_id: dict[int, dm.User] = {}

    async def add(self, user: dm.User) -> dm.User:
        self._by_id[user.id] = user
        return user

    async def get(self, user_id: int) -> dm.User:
        try:
            return self._by_id[user_id]
        except KeyError:
            raise rex.UserNotFound()

    async def update(self, user: dm.User) -> dm.User:
        if user.id not in self._by_id:
            raise rex.UserNotFound()
        self._by_id[user.id] = user
        return user

    async def delete(self, user_id: int) -> None:
        if user_id not in self._by_id:
            raise rex.UserNotFound()
        del self._by_id[user_id]

    async def search(self, params: dm.UserSearchParams) -> list[dm.UserListItem]:
        name = (params.name or "").lower()
        surname = (params.surname or "").lower()
        matches = [
            user
            for user in self._by_id.values()
            if name in user.name.lower() and surname in user.surname.lower()
        ]
        matches.sort(key=lambda user: user.id)
        window = matches[params.offset:params.offset + params.limit]
        return [
            dm.UserListItem(
                id=user.id,
                personal_group_id=user.personal_group_id,
                name=user.name,
                surname=user.surname,
                photo_url=user.photo_url,
            )
            for user in window
        ]


class InMemoryGroupRepository(GroupRepository):
    def __init__(self) -> None:
        self._by_id: dict[int, dm.Group] = {}
        self._next_id = 1

    async def add(self, group: dm.Group) -> dm.Group:
        stored = replace(group, id=self._next_id)
        self._by_id[stored.id] = stored
        self._next_id += 1
        return stored

    async def get(self, group_id: int) -> dm.Group:
        try:
            return self._by_id[group_id]
        except KeyError:
            raise rex.GroupNotFound()

    async def update(self, group: dm.Group) -> dm.Group:
        if group.id not in self._by_id:
            raise rex.GroupNotFound()
        self._by_id[group.id] = group
        return group

    async def delete(self, group_id: int) -> None:
        if group_id not in self._by_id:
            raise rex.GroupNotFound()
        del self._by_id[group_id]

    async def search(self, name: str | None, limit: int, offset: int) -> list[dm.GroupListItem]:
        needle = (name or "").lower()
        matches = [
            group
            for group in self._by_id.values()
            if not group.is_personal and needle in group.name.lower()
        ]
        matches.sort(key=lambda group: group.id)
        return [
            dm.GroupListItem(id=group.id, name=group.name, photo_url=group.photo_url)
            for group in matches[offset:offset + limit]
        ]


class InMemoryPasteRepository(PasteRepository):
    def __init__(self) -> None:
        self._by_id: dict[int, dm.Paste] = {}
        self._next_id = 1

    async def add(self, paste: dm.Paste) -> dm.Paste:
        stored = replace(paste, id=self._next_id)
        self._by_id[stored.id] = stored
        self._next_id += 1
        return stored

    async def get(self, paste_id: int) -> dm.Paste:
        try:
            return self._by_id[paste_id]
        except KeyError:
            raise rex.PasteNotFound()

    async def delete(self, paste_id: int) -> None:
        if paste_id not in self._by_id:
            raise rex.PasteNotFound()
        del self._by_id[paste_id]

    async def list_for_group(self, group_id: int, limit: int, offset: int) -> list[dm.Paste]:
        matches = sorted(
            (paste for paste in self._by_id.values() if paste.group_id == group_id),
            key=lambda paste: paste.id,
        )
        return matches[offset:offset + limit]

    async def paste_ids_for_group(self, group_id: int) -> list[int]:
        return [paste.id for paste in self._by_id.values() if paste.group_id == group_id]

    async def remove_all_for_group(self, group_id: int) -> None:
        doomed = [paste_id for paste_id, paste in self._by_id.items() if paste.group_id == group_id]
        for paste_id in doomed:
            del self._by_id[paste_id]


class InMemoryCommentRepository(CommentRepository):
    def __init__(self) -> None:
        self._by_id: dict[int, dm.Comment] = {}
        self._next_id = 1

    async def add(self, comment: dm.Comment) -> dm.Comment:
        stored = replace(comment, id=self._next_id)
        self._by_id[stored.id] = stored
        self._next_id += 1
        return stored

    async def list_for_paste(self, paste_id: int, limit: int, offset: int) -> list[dm.Comment]:
        matches = sorted(
            (comment for comment in self._by_id.values() if comment.paste_id == paste_id),
            key=lambda comment: comment.id,
        )
        return matches[offset:offset + limit]

    async def remove_all_for_pastes(self, paste_ids: list[int]) -> None:
        doomed = {paste_id for paste_id in paste_ids}
        for comment_id in [c_id for c_id, c in self._by_id.items() if c.paste_id in doomed]:
            del self._by_id[comment_id]


class InMemoryFriendRepository(FriendRepository):
    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo
        self._friends: dict[int, set[int]] = {}

    async def add(self, user_id: int, friend_id: int) -> None:
        if friend_id in self._friends.get(user_id, set()):
            raise rex.AlreadyFriends()
        self._friends.setdefault(user_id, set()).add(friend_id)
        self._friends.setdefault(friend_id, set()).add(user_id)

    async def remove(self, user_id: int, friend_id: int) -> None:
        if friend_id not in self._friends.get(user_id, set()):
            raise rex.FriendshipNotFound()
        self._friends[user_id].discard(friend_id)
        self._friends[friend_id].discard(user_id)

    async def list_friends(self, user_id: int, params: dm.UserSearchParams) -> list[dm.FriendListItem]:
        name = (params.name or "").lower()
        surname = (params.surname or "").lower()
        items: list[dm.FriendListItem] = []
        for friend_id in sorted(self._friends.get(user_id, set())):
            friend = await self._user_repo.get(friend_id)
            if name in friend.name.lower() and surname in friend.surname.lower():
                items.append(
                    dm.FriendListItem(
                        id=friend.id,
                        name=friend.name,
                        surname=friend.surname,
                        photo_url=friend.photo_url,
                    )
                )
        return items[params.offset:params.offset + params.limit]

    async def exists(self, user_id: int, friend_id: int) -> bool:
        return friend_id in self._friends.get(user_id, set())

    async def remove_all_for_user(self, user_id: int) -> None:
        for friend_id in self._friends.pop(user_id, set()):
            self._friends.get(friend_id, set()).discard(user_id)


class InMemorySubscriptionRepository(SubscriptionRepository):
    def __init__(self) -> None:
        self._by_id: dict[int, dm.Subscription] = {}
        self._by_user: dict[int, set[int]] = {}
        self._next_id = 1

    async def add(self, subscription: dm.Subscription) -> dm.Subscription:
        for existing in self._by_id.values():
            if existing.user_id == subscription.user_id and existing.group_id == subscription.group_id:
                raise rex.AlreadySubscribed()
        stored = replace(subscription, id=self._next_id)
        self._by_id[stored.id] = stored
        self._by_user.setdefault(stored.user_id, set()).add(stored.id)
        self._next_id += 1
        return stored

    async def remove(self, user_id: int, subscription_id: int) -> None:
        subscription = self._by_id.get(subscription_id)
        if subscription is None or subscription.user_id != user_id:
            raise rex.SubscriptionNotFound()
        del self._by_id[subscription_id]
        self._by_user.get(user_id, set()).discard(subscription_id)

    async def get(self, subscription_id: int) -> dm.Subscription:
        try:
            return self._by_id[subscription_id]
        except KeyError:
            raise rex.SubscriptionNotFound()

    async def find_for_user_group(self, user_id: int, group_id: int) -> dm.Subscription | None:
        for subscription in self._by_id.values():
            if subscription.user_id == user_id and subscription.group_id == group_id:
                return subscription
        return None

    async def list_for_user(self, user_id: int, limit: int, offset: int) -> list[dm.Subscription]:
        ids = sorted(self._by_user.get(user_id, set()))
        return [self._by_id[i] for i in ids[offset:offset + limit]]

    async def remove_all_for_user(self, user_id: int) -> None:
        for subscription_id in self._by_user.pop(user_id, set()):
            self._by_id.pop(subscription_id, None)

    async def remove_all_for_group(self, group_id: int) -> None:
        doomed = [s_id for s_id, s in self._by_id.items() if s.group_id == group_id]
        for subscription_id in doomed:
            subscription = self._by_id.pop(subscription_id)
            self._by_user.get(subscription.user_id, set()).discard(subscription_id)


class InMemoryChatMemberRepository(ChatMemberRepository):
    def __init__(self) -> None:
        self._members: dict[int, dict[int, bool]] = {}  # chat_id -> {user_id: is_owner}

    async def add(self, member: dm.ChatMember) -> None:
        chat_members = self._members.setdefault(member.chat_id, {})
        if member.user_id in chat_members:
            raise rex.AlreadyMember()
        chat_members[member.user_id] = member.is_owner

    async def remove(self, chat_id: int, user_id: int) -> None:
        chat_members = self._members.get(chat_id, {})
        if user_id not in chat_members:
            raise rex.ChatMemberNotFound()
        del chat_members[user_id]

    async def is_member(self, chat_id: int, user_id: int) -> bool:
        return user_id in self._members.get(chat_id, {})

    async def get(self, chat_id: int, user_id: int) -> dm.ChatMember:
        is_owner = self._members.get(chat_id, {}).get(user_id)
        if is_owner is None:
            raise rex.ChatMemberNotFound()
        return dm.ChatMember(chat_id=chat_id, user_id=user_id, is_owner=is_owner)

    async def list_for_chat(self, chat_id: int, limit: int, offset: int) -> list[dm.ChatMember]:
        user_ids = sorted(self._members.get(chat_id, {}))
        window = user_ids[offset:offset + limit]
        return [
            dm.ChatMember(chat_id=chat_id, user_id=user_id,
                          is_owner=self._members[chat_id][user_id])
            for user_id in window
        ]

    async def chat_ids_for_user(self, user_id: int) -> list[int]:
        return sorted(
            chat_id for chat_id, members in self._members.items() if user_id in members
        )

    async def user_ids_for_chat(self, chat_id: int) -> list[int]:
        return sorted(self._members.get(chat_id, {}))

    async def remove_all_for_chat(self, chat_id: int) -> None:
        self._members.pop(chat_id, None)

    async def remove_user_from_chat(self, chat_id: int, user_id: int) -> None:
        self._members.get(chat_id, {}).pop(user_id, None)


class InMemoryChatRepository(ChatRepository):
    def __init__(self, member_repo: ChatMemberRepository) -> None:
        self._member_repo = member_repo
        self._by_id: dict[int, dm.Chat] = {}
        self._next_id = 1

    async def add(self, chat: dm.Chat) -> dm.Chat:
        stored = replace(chat, id=self._next_id)
        self._by_id[stored.id] = stored
        self._next_id += 1
        return stored

    async def get(self, chat_id: int) -> dm.Chat:
        try:
            return self._by_id[chat_id]
        except KeyError:
            raise rex.ChatNotFound()

    async def delete(self, chat_id: int) -> None:
        self._by_id.pop(chat_id, None)

    async def list_for_user(self, user_id: int, limit: int, offset: int) -> list[dm.Chat]:
        chat_ids = await self._member_repo.chat_ids_for_user(user_id)
        window = chat_ids[offset:offset + limit]
        return [self._by_id[chat_id] for chat_id in window if chat_id in self._by_id]

    async def find_personal_chat(self, user_a: int, user_b: int) -> dm.Chat | None:
        for chat in self._by_id.values():
            if chat.chat_type != dm.ChatType.PERSONAL:
                continue
            members = await self._member_repo.user_ids_for_chat(chat.id)
            if len(members) == 2 and user_a in members and user_b in members:
                return chat
        return None


class InMemoryMessageRepository(MessageRepository):
    def __init__(self) -> None:
        self._by_id: dict[int, dm.Message] = {}
        self._next_id = 1

    async def add(self, message: dm.Message) -> dm.Message:
        stored = replace(message, id=self._next_id)
        self._by_id[stored.id] = stored
        self._next_id += 1
        return stored

    async def list_for_chat(self, chat_id: int, limit: int, offset: int) -> list[dm.Message]:
        matches = sorted(
            (message for message in self._by_id.values() if message.chat_id == chat_id),
            key=lambda message: message.id,
        )
        return matches[offset:offset + limit]

    async def remove_all_for_chat(self, chat_id: int) -> None:
        doomed = [m_id for m_id, m in self._by_id.items() if m.chat_id == chat_id]
        for message_id in doomed:
            del self._by_id[message_id]


class InMemoryMediaRepository(MediaRepository):
    def __init__(self) -> None:
        self._by_id: dict[int, dm.MediaFile] = {}
        self._next_id = 1

    async def add(self, media: dm.MediaFile) -> dm.MediaFile:
        stored = replace(media, id=self._next_id)
        self._by_id[stored.id] = stored
        self._next_id += 1
        return stored

    async def get(self, media_id: int) -> dm.MediaFile:
        try:
            return self._by_id[media_id]
        except KeyError:
            raise rex.MediaNotFound()
