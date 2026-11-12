"""Composition root: builds repositories, services and wires them together.

Two data-layer modes, selected by ``Settings.database_url``:
  - empty (default): in-memory repositories (the mock data layer);
  - a sqlalchemy URL (e.g. postgresql+asyncpg://...): SQLAlchemy
    implementations behind the same interfaces.

A fresh Container per create_app() call keeps all state inside the app
instance, which makes tests trivially isolated. ``await container.setup()``
creates the database schema in DB mode (called from the app lifespan);
in-memory mode needs no setup.
"""

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.admins import AdminRegistry
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
from app.repositories.memory.memory_repositories import (
    InMemoryAccountRepository,
    InMemoryChatMemberRepository,
    InMemoryChatRepository,
    InMemoryCommentRepository,
    InMemoryFriendRepository,
    InMemoryGroupRepository,
    InMemoryMediaRepository,
    InMemoryMessageRepository,
    InMemoryPasteRepository,
    InMemorySubscriptionRepository,
    InMemoryUserRepository,
)
from app.repositories.sqlalchemy_repos import orm
from app.repositories.sqlalchemy_repos.engine import (
    build_sessionmaker,
    create_schema,
    dispose,
)
from app.repositories.sqlalchemy_repos.repositories import build_sqlalchemy_repos
from app.realtime.hub import WebSocketHub
from app.services.auth_service import AuthService
from app.services.chat_service import ChatService
from app.services.group_service import GroupService
from app.services.media_service import MediaService
from app.services.ports import ChatEventPublisher
from app.services.paste_service import PasteService
from app.services.sign_service import SignService
from app.services.user_service import UserService
from app.settings import Settings


@dataclass
class Container:
    settings: Settings
    account_repo: AccountRepository
    user_repo: UserRepository
    group_repo: GroupRepository
    friend_repo: FriendRepository
    subscription_repo: SubscriptionRepository
    paste_repo: PasteRepository
    comment_repo: CommentRepository
    chat_repo: ChatRepository
    chat_member_repo: ChatMemberRepository
    message_repo: MessageRepository
    media_repo: MediaRepository
    auth_service: AuthService
    sign_service: SignService
    user_service: UserService
    group_service: GroupService
    paste_service: PasteService
    chat_service: ChatService
    media_service: MediaService
    chat_events: ChatEventPublisher
    sessionmaker: Optional[async_sessionmaker] = None

    async def setup(self) -> None:
        """Idempotent bootstrap: creates the schema in database mode."""
        if self.sessionmaker is not None:
            await create_schema(self.sessionmaker)

    async def shutdown(self) -> None:
        if self.sessionmaker is not None:
            await dispose(self.sessionmaker)


def _build_repos(settings: Settings) -> dict:
    if settings.database_url:
        return build_sqlalchemy_repos(settings.database_url)
    user_repo = InMemoryUserRepository()
    return {
        "sessionmaker": None,
        "account_repo": InMemoryAccountRepository(),
        "user_repo": user_repo,
        "group_repo": InMemoryGroupRepository(),
        "friend_repo": InMemoryFriendRepository(user_repo),
        "subscription_repo": InMemorySubscriptionRepository(),
        "paste_repo": InMemoryPasteRepository(),
        "comment_repo": InMemoryCommentRepository(),
        "chat_member_repo": InMemoryChatMemberRepository(),
        "chat_repo": None,  # needs the member repo, built below
        "message_repo": InMemoryMessageRepository(),
        "media_repo": InMemoryMediaRepository(),
    }


def build_container(settings: Settings | None = None,
                    admins: AdminRegistry | None = None) -> Container:
    settings = settings or Settings()
    admins = admins or AdminRegistry.from_file(settings.admins_file)

    repos = _build_repos(settings)
    if settings.database_url:
        chat_repo = repos["chat_repo"]
    else:
        chat_repo = InMemoryChatRepository(repos["chat_member_repo"])
    repos["chat_repo"] = chat_repo

    account_repo = repos["account_repo"]
    user_repo = repos["user_repo"]
    group_repo = repos["group_repo"]
    friend_repo = repos["friend_repo"]
    subscription_repo = repos["subscription_repo"]
    paste_repo = repos["paste_repo"]
    comment_repo = repos["comment_repo"]
    chat_member_repo = repos["chat_member_repo"]
    message_repo = repos["message_repo"]
    media_repo = repos["media_repo"]

    auth_service = AuthService(settings)
    sign_service = SignService(
        account_repo, user_repo, group_repo, auth_service, admins, settings
    )
    group_service = GroupService(group_repo, paste_repo, comment_repo, subscription_repo)
    paste_service = PasteService(
        paste_repo, comment_repo, group_repo, subscription_repo, user_repo
    )
    chat_events = WebSocketHub()
    chat_service = ChatService(chat_repo, chat_member_repo, message_repo, user_repo, chat_events)
    media_service = MediaService(media_repo, settings)
    user_service = UserService(
        account_repo, user_repo, group_repo, friend_repo, subscription_repo,
        group_service, chat_service,
    )
    return Container(
        settings=settings,
        account_repo=account_repo,
        user_repo=user_repo,
        group_repo=group_repo,
        friend_repo=friend_repo,
        subscription_repo=subscription_repo,
        paste_repo=paste_repo,
        comment_repo=comment_repo,
        chat_repo=chat_repo,
        chat_member_repo=chat_member_repo,
        message_repo=message_repo,
        media_repo=media_repo,
        auth_service=auth_service,
        sign_service=sign_service,
        user_service=user_service,
        group_service=group_service,
        paste_service=paste_service,
        chat_service=chat_service,
        media_service=media_service,
        chat_events=chat_events,
        sessionmaker=repos["sessionmaker"],
    )
