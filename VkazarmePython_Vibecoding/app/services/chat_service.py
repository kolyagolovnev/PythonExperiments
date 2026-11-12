"""Chats and messages.

Rules (the spec leaves most of them open; these are documented decisions):
- a personal chat is a fixed 1:1 pair, created idempotently: a second
  create for the same pair returns the existing chat; its members cannot
  be changed afterwards;
- a public chat is created by an owner (the caller); any member may add
  further members; the `is_owner` flag of the add-member body is ignored
  (ownership is assigned at creation only);
- members can leave a public chat; the owner can remove anyone except
  themself (an owner cannot leave - delete the chat instead); the owner
  cannot be removed by anyone;
- reading a chat, its members and messages, and sending messages is for
  members only (403 otherwise);
- when a user is deleted (admin cascade), their memberships disappear and
  personal chats that lose one of the two members are deleted with their
  messages.

Realtime delivery is a separate AsyncAPI/WebSocket concern and is not part
of this REST milestone.
"""

from datetime import datetime, timezone

from app.domains import models as dm
from app.repositories.interfaces import (
    ChatMemberRepository,
    ChatRepository,
    MessageRepository,
    UserRepository,
)
from app.services.exceptions import (
    CannotRemoveOwner,
    ChatNotFound,
    InvalidChatMembers,
    PermissionDenied,
    PersonalChatFixed,
)
from app.services.ports import (
    ChatEventPublisher,
    JOINED,
    KICKED,
    LEFT,
)


class ChatService:
    def __init__(
        self,
        chat_repo: ChatRepository,
        member_repo: ChatMemberRepository,
        message_repo: MessageRepository,
        user_repo: UserRepository,
        events: ChatEventPublisher,
    ):
        self._chat_repo = chat_repo
        self._member_repo = member_repo
        self._message_repo = message_repo
        self._user_repo = user_repo
        self._events = events

    # --- chats ---

    async def list_chats(self, requester: dm.AuthToken, limit: int,
                         offset: int) -> list[dm.ChatListItem]:
        chats = await self._chat_repo.list_for_user(requester.sub, limit, offset)
        items: list[dm.ChatListItem] = []
        for chat in chats:
            items.append(await self._to_list_item(chat, requester.sub))
        return items

    async def create_chat(self, requester: dm.AuthToken, name: str,
                          chat_type: dm.ChatType, users: list[int],
                          photo_url: str) -> dm.Chat:
        others = [user_id for user_id in dict.fromkeys(users) if user_id != requester.sub]
        for user_id in others:
            await self._user_repo.get(user_id)  # UserNotFound -> 404

        if chat_type == dm.ChatType.PERSONAL:
            if len(others) != 1:
                raise InvalidChatMembers()
            existing = await self._chat_repo.find_personal_chat(requester.sub, others[0])
            if existing is not None:
                return existing  # idempotent create
            chat = await self._chat_repo.add(
                dm.Chat(id=0, name=name, photo_url=photo_url,
                        chat_type=chat_type, owner_id=None)
            )
            await self._member_repo.add(dm.ChatMember(chat.id, requester.sub, is_owner=False))
            await self._member_repo.add(dm.ChatMember(chat.id, others[0], is_owner=False))
            return chat

        chat = await self._chat_repo.add(
            dm.Chat(id=0, name=name, photo_url=photo_url,
                    chat_type=chat_type, owner_id=requester.sub)
        )
        await self._member_repo.add(dm.ChatMember(chat.id, requester.sub, is_owner=True))
        for user_id in others:
            await self._member_repo.add(dm.ChatMember(chat.id, user_id, is_owner=False))
        return chat

    async def get_chat(self, requester: dm.AuthToken, chat_id: int) -> dm.Chat:
        chat = await self._chat_repo.get(chat_id)  # ChatNotFound -> 404
        await self._ensure_member(chat_id, requester.sub)
        return chat

    # --- members ---

    async def list_members(self, requester: dm.AuthToken, chat_id: int,
                           limit: int, offset: int) -> list[dm.ChatMemberListItem]:
        await self._chat_repo.get(chat_id)
        await self._ensure_member(chat_id, requester.sub)
        items: list[dm.ChatMemberListItem] = []
        for member in await self._member_repo.list_for_chat(chat_id, limit, offset):
            user = await self._user_repo.get(member.user_id)
            items.append(dm.ChatMemberListItem(
                user=self._to_user_item(user), is_owner=member.is_owner,
            ))
        return items

    async def add_member(self, requester: dm.AuthToken, chat_id: int,
                         user_id: int) -> None:
        chat = await self._chat_repo.get(chat_id)
        if chat.chat_type == dm.ChatType.PERSONAL:
            raise PersonalChatFixed()
        await self._user_repo.get(user_id)  # UserNotFound -> 404
        await self._ensure_member(chat_id, requester.sub)  # only members may invite
        await self._member_repo.add(
            dm.ChatMember(chat_id=chat_id, user_id=user_id, is_owner=False)
        )  # AlreadyMember -> 400
        await self._events.publish_member_change(chat_id, JOINED, user_id)

    async def remove_member(self, requester: dm.AuthToken, chat_id: int,
                            member_id: int) -> None:
        chat = await self._chat_repo.get(chat_id)
        if chat.chat_type == dm.ChatType.PERSONAL:
            raise PersonalChatFixed()
        if member_id == chat.owner_id:
            raise CannotRemoveOwner()
        is_self = requester.sub == member_id
        if not is_self and requester.sub != chat.owner_id:
            raise PermissionDenied()
        await self._user_repo.get(member_id)  # UserNotFound -> 404
        await self._member_repo.remove(chat_id, member_id)  # ChatMemberNotFound -> 404
        action = LEFT if is_self else KICKED
        await self._events.publish_member_change(chat_id, action, member_id)

    # --- messages ---

    async def list_messages(self, requester: dm.AuthToken, chat_id: int,
                            limit: int, offset: int) -> list[dm.Message]:
        await self._chat_repo.get(chat_id)
        await self._ensure_member(chat_id, requester.sub)
        return await self._message_repo.list_for_chat(chat_id, limit, offset)

    async def send_message(self, requester: dm.AuthToken, chat_id: int,
                           text: str) -> dm.Message:
        await self._chat_repo.get(chat_id)
        await self._ensure_member(chat_id, requester.sub)
        message = await self._message_repo.add(
            dm.Message(id=0, chat_id=chat_id, author_id=requester.sub,
                       text=text, time=datetime.now(timezone.utc))
        )
        await self._events.publish_message(message)
        return message

    # --- cascade (internal, no requester) ---

    async def remove_user_from_all_chats(self, user_id: int) -> None:
        """Called when an admin deletes a user: memberships disappear and
        personal chats that lose one of their two members are deleted with
        their messages."""
        for chat_id in await self._member_repo.chat_ids_for_user(user_id):
            chat = await self._chat_repo.get(chat_id)
            await self._member_repo.remove_user_from_chat(chat_id, user_id)
            if chat.chat_type == dm.ChatType.PERSONAL:
                await self._message_repo.remove_all_for_chat(chat_id)
                await self._member_repo.remove_all_for_chat(chat_id)
                await self._chat_repo.delete(chat_id)

    # --- helpers ---

    async def _ensure_member(self, chat_id: int, user_id: int) -> None:
        if not await self._member_repo.is_member(chat_id, user_id):
            raise PermissionDenied()

    async def _to_list_item(self, chat: dm.Chat, viewer_id: int) -> dm.ChatListItem:
        if chat.chat_type == dm.ChatType.PERSONAL:
            # a personal chat is shown to each participant under the other
            # participant's name/photo, like in messengers
            for user_id in await self._member_repo.user_ids_for_chat(chat.id):
                if user_id != viewer_id:
                    other = await self._user_repo.get(user_id)
                    return dm.ChatListItem(
                        id=chat.id, name=f"{other.name} {other.surname}".strip(),
                        photo_url=other.photo_url,
                    )
        return dm.ChatListItem(id=chat.id, name=chat.name, photo_url=chat.photo_url)

    @staticmethod
    def _to_user_item(user: dm.User) -> dm.UserListItem:
        return dm.UserListItem(
            id=user.id,
            personal_group_id=user.personal_group_id,
            name=user.name,
            surname=user.surname,
            photo_url=user.photo_url,
        )
