"""Pydantic DTOs for /chats endpoints (chats, members, messages)."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.domains import models as dm
from app.dto.user_dto import UserListItemDTO


class ChatListItemDTO(BaseModel):
    id: int
    name: str
    photo_url: str

    @classmethod
    def from_entity(cls, item: dm.ChatListItem) -> "ChatListItemDTO":
        return cls(id=item.id, name=item.name, photo_url=item.photo_url)


class ChatPostDTO(BaseModel):
    """Body of POST /chats.

    The spec marks `name` and `photo_url` required, but a personal 1:1 chat
    has no meaningful client-supplied name (it is rendered from the other
    participant), so both are optional here. `users` holds the *other*
    participants: exactly one for `personal` (the caller is added
    automatically), any list for `public` (the caller becomes the owner).
    """

    name: str = ""
    chat_type: Literal["personal", "public"]
    users: list[int] = Field(default_factory=list)
    photo_url: str = ""


class ChatDTO(BaseModel):
    id: int
    name: str
    photo_url: str
    chat_type: Literal["personal", "public"]

    @classmethod
    def from_entity(cls, chat: dm.Chat) -> "ChatDTO":
        return cls(id=chat.id, name=chat.name, photo_url=chat.photo_url,
                   chat_type=chat.chat_type.value)


class ChatMemberPostDTO(BaseModel):
    """Body of POST /chats/{ChatID}/members (the spec's `ChatMember`).
    `is_owner` is accepted for spec compatibility but ignored: ownership is
    assigned at chat creation only."""

    user_id: int
    is_owner: bool = False


class ChatMemberListItemDTO(BaseModel):
    user: UserListItemDTO
    is_owner: bool

    @classmethod
    def from_entity(cls, item: dm.ChatMemberListItem) -> "ChatMemberListItemDTO":
        return cls(user=UserListItemDTO.from_entity(item.user), is_owner=item.is_owner)


class MessagePostDTO(BaseModel):
    """Body of the message POST. The spec references the full `Message`
    schema, whose id/author/time are server-generated; only text is accepted."""

    text: str = Field(min_length=1)


class MessageDTO(BaseModel):
    # `user_id` is the message author (the spec's required list says `user_id`,
    # its property list says `chat_member_id` — `user_id` was chosen).
    id: int
    user_id: int
    text: str
    time: datetime

    @classmethod
    def from_entity(cls, message: dm.Message) -> "MessageDTO":
        return cls(id=message.id, user_id=message.author_id,
                   text=message.text, time=message.time)
