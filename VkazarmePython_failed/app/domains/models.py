from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Literal

#TODO: Нужно прописать везде post_init, который проверяет данные на корректность:

# --- Enums ---

@dataclass 
class SignInInit:
    state: str

#TODO: Может как-нибудь переделать enum под числа?
class Provider(Enum):
    VK = "vk"
    GOOGLE = "google"
    SELF = "self"


class SubType(Enum):
    GROUP = "group"
    USER = "user"


class ChatType(Enum):
    PERSONAL = "personal"
    PUBLIC = "public"


# --- Sign-related ---

@dataclass
class OAuthCallback:
    code: str
    state: str

@dataclass
class AuthToken:
    sub: str
    exp: int
    #role: Literal['user', 'admin']

@dataclass
class SignRequest:
    email: str
    password: str

    def __post_init__(self):
        # Здесь можно добавить валидацию email и длины пароля, если нужно
        pass

@dataclass
class SignUpData:
    email: str
    password: str

    def __post_init__(self):
        # Здесь можно добавить валидацию email и длины пароля, если нужно
        pass

@dataclass
class TempAccountData:
    email: str
    hashed_password: bytes
    key: str
    oauth_provider: Provider
    oauth_id: str #TODO: Или стоит использовать int?


# --- List items ---

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


@dataclass
class GroupListItem:
    id: int
    name: str
    photo_url: str


@dataclass
class ChatListItem:
    id: int
    name: str
    photo_url: str


@dataclass
class ChatMemberListItem:
    user: UserListItem
    is_owner: bool


# --- Subscription ---

@dataclass
class SubscriptionListItem:
    sub_type: SubType
    group_id: int
    user_id: int  # по описанию: если sub_type == group, то user_id == -1
    name: str
    is_moderator: Optional[bool] = None
    photo_url: str = ""


# --- Patch models ---

@dataclass
class UserPatch:
    name: Optional[str] = None
    surname: Optional[str] = None
    job: Optional[str] = None
    rang: Optional[int] = None
    status: Optional[str] = None
    subdivision: Optional[str] = None
    photo_url: Optional[str] = None


@dataclass
class GroupPatch:
    name: Optional[str] = None
    description: Optional[str] = None
    photo_url: Optional[str] = None


# --- Core entities ---

@dataclass
class User:
    id: int
    name: str
    surname: str
    job: str
    rang: int
    status: str
    subdivision: str
    photo_url: str


@dataclass
class Comment:
    id: int
    paste_id: Optional[int] = None
    text: str = ""
    time: str = ""
    author: UserListItem = UserListItem()


@dataclass
class Paste:
    id: int
    group_id: int
    text: str = ""
    time: str = ""


@dataclass
class Group:
    id: int
    name: str = ""
    description: str = ""
    photo_url: str = ""


@dataclass
class Message:
    id: int
    chat_member_id: Optional[int] = None
    text: str = ""
    time: str = ""


@dataclass
class ChatMember:
    user_id: int
    is_owner: bool = False


@dataclass
class Chat:
    id: int
    name: str = ""
    photo_url: str = ""
    chat_type: ChatType = ChatType.PERSONAL


# --- Post models ---

@dataclass
class FriendPost:
    user_id: int


@dataclass
class SubscriptionPost:
    group_id: int
    is_moderator: Optional[bool] = None


@dataclass
class ChatPost:
    name: str
    chat_type: ChatType
    users: List[int]
    photo_url: str = ""


@dataclass
class Media:
    photo_url: Optional[str] = None


# --- RootModel-based models ---
# В dataclass нет аналога RootModel. Ниже — разумные замены.

# Friend(RootModel[Any]) -> если это просто список друзей, то List[FriendListItem]
# Если это «любой JSON», то лучше использовать прямой тип, например, dict или list.
# Здесь я предполагаю, что это список объектов FriendListItem:
@dataclass
class Friends:
    items: List[FriendListItem] = field(default_factory=list)


# PastePost(RootModel[Any]) и Subscription(RootModel[Any]) — аналогично.
# Если они использовались как «обёртка» над одним объектом, то можно убрать dataclass и использовать сам тип.
# Ниже — примеры, если это «список» или «один объект».

# Если PastePost был обёрткой над одним Paste:
PastePost = Paste  # можно использовать напрямую

# Если Subscription был обёрткой над списком SubscriptionListItem:
@dataclass
class Subscriptions:
    items: List[SubscriptionListItem] = field(default_factory=list)