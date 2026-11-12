"""Repository interfaces.

Services depend only on these ABCs; concrete implementations
(in-memory today, SQLAlchemy later) are wired in app/container.py.
"""

from abc import ABC, abstractmethod

from app.domains import models as dm


class AccountRepository(ABC):
    @abstractmethod
    async def add(self, account: dm.Account) -> dm.Account:
        """Persists the account, assigns its id, returns the stored copy."""

    @abstractmethod
    async def find_by_email(self, email: str) -> dm.Account | None:
        """Case-insensitive lookup; None when the email is unknown."""

    @abstractmethod
    async def get(self, account_id: int) -> dm.Account:
        """Raises AccountNotFound when the id is unknown."""

    @abstractmethod
    async def delete(self, account_id: int) -> None:
        """Raises AccountNotFound when the id is unknown."""


class UserRepository(ABC):
    @abstractmethod
    async def add(self, user: dm.User) -> dm.User:
        """Persists the user, returns the stored copy (id is provided by the caller)."""

    @abstractmethod
    async def get(self, user_id: int) -> dm.User:
        """Raises UserNotFound when the id is unknown."""

    @abstractmethod
    async def update(self, user: dm.User) -> dm.User:
        """Overwrites the stored user; raises UserNotFound when unknown."""

    @abstractmethod
    async def delete(self, user_id: int) -> None:
        """Raises UserNotFound when the id is unknown."""

    @abstractmethod
    async def search(self, params: dm.UserSearchParams) -> list[dm.UserListItem]:
        """Case-insensitive substring match on name/surname, ordered by id,
        sliced by offset/limit."""


class GroupRepository(ABC):
    @abstractmethod
    async def add(self, group: dm.Group) -> dm.Group:
        """Persists the group, assigns its id, returns the stored copy."""

    @abstractmethod
    async def get(self, group_id: int) -> dm.Group:
        """Raises GroupNotFound when the id is unknown."""

    @abstractmethod
    async def update(self, group: dm.Group) -> dm.Group:
        """Overwrites the stored group; raises GroupNotFound when unknown."""

    @abstractmethod
    async def delete(self, group_id: int) -> None:
        """Raises GroupNotFound when the id is unknown."""

    @abstractmethod
    async def search(self, name: str | None, limit: int, offset: int) -> list[dm.GroupListItem]:
        """Case-insensitive substring match on the name, ordered by id, sliced.
        Personal groups are not listed (they are discovered via users)."""


class PasteRepository(ABC):
    @abstractmethod
    async def add(self, paste: dm.Paste) -> dm.Paste:
        """Persists the paste, assigns its id, returns the stored copy."""

    @abstractmethod
    async def get(self, paste_id: int) -> dm.Paste:
        """Raises PasteNotFound when the id is unknown."""

    @abstractmethod
    async def delete(self, paste_id: int) -> None:
        """Raises PasteNotFound when the id is unknown."""

    @abstractmethod
    async def list_for_group(self, group_id: int, limit: int, offset: int) -> list[dm.Paste]:
        """The group's pastes ordered by id, sliced by offset/limit."""

    @abstractmethod
    async def paste_ids_for_group(self, group_id: int) -> list[int]:
        """All paste ids of the group (used for cascading comment deletion)."""

    @abstractmethod
    async def remove_all_for_group(self, group_id: int) -> None:
        """Drops the group's pastes (used on group deletion)."""


class CommentRepository(ABC):
    @abstractmethod
    async def add(self, comment: dm.Comment) -> dm.Comment:
        """Persists the comment, assigns its id, returns the stored copy."""

    @abstractmethod
    async def list_for_paste(self, paste_id: int, limit: int, offset: int) -> list[dm.Comment]:
        """The paste's comments ordered by id, sliced by offset/limit."""

    @abstractmethod
    async def remove_all_for_pastes(self, paste_ids: list[int]) -> None:
        """Drops the comments of the given pastes (used on paste/group deletion)."""


class ChatMemberRepository(ABC):
    @abstractmethod
    async def add(self, member: dm.ChatMember) -> None:
        """Adds a membership; raises AlreadyMember when it exists."""

    @abstractmethod
    async def remove(self, chat_id: int, user_id: int) -> None:
        """Raises ChatMemberNotFound when the membership is absent."""

    @abstractmethod
    async def is_member(self, chat_id: int, user_id: int) -> bool: ...

    @abstractmethod
    async def get(self, chat_id: int, user_id: int) -> dm.ChatMember:
        """Raises ChatMemberNotFound when the membership is absent."""

    @abstractmethod
    async def list_for_chat(self, chat_id: int, limit: int, offset: int) -> list[dm.ChatMember]:
        """The chat's memberships ordered by user id, sliced by offset/limit."""

    @abstractmethod
    async def chat_ids_for_user(self, user_id: int) -> list[int]:
        """Ids of the chats the user is a member of, ordered by chat id."""

    @abstractmethod
    async def user_ids_for_chat(self, chat_id: int) -> list[int]:
        """Ids of the chat's members, ordered by user id."""

    @abstractmethod
    async def remove_all_for_chat(self, chat_id: int) -> None: ...

    @abstractmethod
    async def remove_user_from_chat(self, chat_id: int, user_id: int) -> None:
        """Silently drops the membership if present (cascade helper)."""


class ChatRepository(ABC):
    @abstractmethod
    async def add(self, chat: dm.Chat) -> dm.Chat:
        """Persists the chat, assigns its id, returns the stored copy."""

    @abstractmethod
    async def get(self, chat_id: int) -> dm.Chat:
        """Raises ChatNotFound when the id is unknown."""

    @abstractmethod
    async def delete(self, chat_id: int) -> None: ...

    @abstractmethod
    async def list_for_user(self, user_id: int, limit: int, offset: int) -> list[dm.Chat]:
        """Chats the user is a member of, ordered by chat id, sliced."""

    @abstractmethod
    async def find_personal_chat(self, user_a: int, user_b: int) -> dm.Chat | None:
        """The personal chat between the two users, or None."""


class MessageRepository(ABC):
    @abstractmethod
    async def add(self, message: dm.Message) -> dm.Message:
        """Persists the message, assigns its id, returns the stored copy."""

    @abstractmethod
    async def list_for_chat(self, chat_id: int, limit: int, offset: int) -> list[dm.Message]:
        """The chat's messages ordered by id (oldest first), sliced."""

    @abstractmethod
    async def remove_all_for_chat(self, chat_id: int) -> None: ...


class MediaRepository(ABC):
    @abstractmethod
    async def add(self, media: dm.MediaFile) -> dm.MediaFile:
        """Persists the file, assigns its id, returns the stored copy."""

    @abstractmethod
    async def get(self, media_id: int) -> dm.MediaFile:
        """Raises MediaNotFound when the id is unknown."""


class FriendRepository(ABC):
    @abstractmethod
    async def add(self, user_id: int, friend_id: int) -> None:
        """Creates a symmetric friendship; raises AlreadyFriends if it exists."""

    @abstractmethod
    async def remove(self, user_id: int, friend_id: int) -> None:
        """Removes the symmetric friendship; raises FriendshipNotFound if absent."""

    @abstractmethod
    async def list_friends(self, user_id: int, params: dm.UserSearchParams) -> list[dm.FriendListItem]:
        """Friend projections filtered by name/surname, ordered by id, sliced."""

    @abstractmethod
    async def exists(self, user_id: int, friend_id: int) -> bool: ...

    @abstractmethod
    async def remove_all_for_user(self, user_id: int) -> None:
        """Drops every friendship of the user (used on account deletion)."""


class SubscriptionRepository(ABC):
    @abstractmethod
    async def add(self, subscription: dm.Subscription) -> dm.Subscription:
        """Persists the subscription, assigns its id; raises AlreadySubscribed
        when the (user_id, group_id) pair already exists."""

    @abstractmethod
    async def remove(self, user_id: int, subscription_id: int) -> None:
        """Removes the user's subscription; raises SubscriptionNotFound if absent."""

    @abstractmethod
    async def get(self, subscription_id: int) -> dm.Subscription:
        """Raises SubscriptionNotFound when the id is unknown."""

    @abstractmethod
    async def find_for_user_group(self, user_id: int, group_id: int) -> dm.Subscription | None:
        """The user's subscription to the group, or None."""

    @abstractmethod
    async def list_for_user(self, user_id: int, limit: int, offset: int) -> list[dm.Subscription]:
        """The user's subscriptions ordered by id, sliced by offset/limit."""

    @abstractmethod
    async def remove_all_for_user(self, user_id: int) -> None:
        """Drops the user's own subscriptions (used on account deletion)."""

    @abstractmethod
    async def remove_all_for_group(self, group_id: int) -> None:
        """Drops everyone's subscriptions to the group (used on group deletion)."""
