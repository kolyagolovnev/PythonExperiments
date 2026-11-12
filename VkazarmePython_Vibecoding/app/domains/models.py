"""Domain models (framework-agnostic dataclasses).

These are the entities the services and repositories operate on.
API-facing Pydantic DTOs live in app/dto and are converted to/from
these models at the boundary.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class Role(str, Enum):
    USER = "user"
    ADMIN = "admin"


class SubType(str, Enum):
    GROUP = "group"
    USER = "user"


class ChatType(str, Enum):
    PERSONAL = "personal"
    PUBLIC = "public"


# --- Sign / account ---

@dataclass
class SignUpData:
    email: str
    password: str


@dataclass
class SignInRequest:
    email: str
    password: str


@dataclass
class Account:
    id: int
    email: str
    hashed_password: bytes
    role: Role


@dataclass
class AuthToken:
    """JWT access token payload plus the encoded token itself."""
    sub: int
    exp: int
    role: Role
    raw: str = ""


# --- User ---

@dataclass
class User:
    id: int
    personal_group_id: int
    name: str = "Noname"
    surname: str = "Nosurname"
    job: str = "Unknown job"
    rang: int = 0
    status: str = "Unknown status"
    subdivision: str = "Unknown subdivision"
    photo_url: str = ""


@dataclass
class UserPatch:
    """Fields left as None are not provided (merge-patch semantics)."""
    name: Optional[str] = None
    surname: Optional[str] = None
    job: Optional[str] = None
    rang: Optional[int] = None
    status: Optional[str] = None
    subdivision: Optional[str] = None
    photo_url: Optional[str] = None


@dataclass
class UserSearchParams:
    name: Optional[str]
    surname: Optional[str]
    limit: int
    offset: int


@dataclass
class UserListItem:
    id: int
    personal_group_id: int
    name: str
    surname: str
    photo_url: str


@dataclass
class FriendListItem:
    id: int
    name: str
    surname: str
    photo_url: str


# --- Group (minimal for milestone 1) ---

@dataclass
class Group:
    id: int
    name: str
    description: str = ""
    photo_url: str = ""
    owner_id: Optional[int] = None  # set for personal groups, None for topic groups

    @property
    def is_personal(self) -> bool:
        return self.owner_id is not None


@dataclass
class GroupListItem:
    id: int
    name: str
    photo_url: str


@dataclass
class GroupPost:
    """Body of POST /groups (id is server-assigned)."""
    name: str
    description: str = ""
    photo_url: str = ""


@dataclass
class GroupPatch:
    """Fields left as None are not provided (merge-patch semantics)."""
    name: Optional[str] = None
    description: Optional[str] = None
    photo_url: Optional[str] = None


# --- Pastes (posts) and comments ---

@dataclass
class Paste:
    id: int
    group_id: int
    author_id: int  # not in the spec's Paste schema; used for permission checks
    text: str
    time: datetime


@dataclass
class Comment:
    id: int
    paste_id: int
    author_id: int
    text: str
    time: datetime


@dataclass
class CommentListItem:
    """Comment as returned by the API (spec's Comment schema: author is a UserListItem)."""
    id: int
    paste_id: int
    text: str
    time: datetime
    author: UserListItem


# --- Subscription ---

@dataclass
class Subscription:
    id: int
    user_id: int  # subscriber
    group_id: int
    is_moderator: bool = False


@dataclass
class SubscriptionListItem:
    # `id` is not in the spec's schema, but DELETE
    # /users/{UserID}/subscriptions/{SubscriptionID} is unusable
    # unless the list exposes the subscription identifiers.
    id: int
    sub_type: SubType
    group_id: int
    user_id: int  # -1 for group subscriptions, owner id for user subscriptions
    name: str
    is_moderator: bool
    photo_url: str


# --- Chats and messages ---

@dataclass
class Chat:
    id: int
    name: str
    photo_url: str
    chat_type: ChatType
    owner_id: Optional[int] = None  # creator, for public chats; None for personal


@dataclass
class ChatListItem:
    id: int
    name: str
    photo_url: str


@dataclass
class ChatMember:
    chat_id: int
    user_id: int
    is_owner: bool


@dataclass
class ChatMemberListItem:
    user: UserListItem
    is_owner: bool


@dataclass
class Message:
    id: int
    chat_id: int
    author_id: int
    text: str
    time: datetime


# --- Media ---

@dataclass
class MediaFile:
    id: int
    filename: str
    content_type: str
    data: bytes
