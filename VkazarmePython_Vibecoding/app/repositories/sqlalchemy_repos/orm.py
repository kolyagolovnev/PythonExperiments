"""SQLAlchemy 2.0 ORM models for the database-backed repositories.

Deliberately **no foreign-key constraints**: referential integrity is
owned by the services (they orchestrate the cascades and keep identical
semantics across the in-memory and database implementations — e.g. the
messages of a deleted user survive in public chats, which an FK would
forbid). The database enforces only the uniqueness rules that the
repository interfaces themselves promise:
  - accounts: unique lower(email)
  - friendships: PK (user_id, friend_id), both directions stored
  - subscriptions: unique (user_id, group_id)
  - chat_members: PK (chat_id, user_id)

Everything else is plain indexed integer columns. The SQL is kept portable
(lower().like() instead of ILIKE, LargeBinary instead of BYTEA) so the same
repositories run on PostgreSQL in production and SQLite in tests.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, LargeBinary, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from app.domains import models as dm


class UTCDateTime(TypeDecorator):
    """Stores naive UTC timestamps, always returns timezone-aware UTC.

    The domain models carry aware UTC datetimes; asyncpg refuses to encode
    them into a TIMESTAMP WITHOUT TIME ZONE column, and SQLite would silently
    drop the tzinfo on read. Normalizing on both sides keeps the two backends
    byte-for-byte comparable."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return None

    def process_result_value(self, value, dialect):
        if value is not None:
            return value.replace(tzinfo=timezone.utc)
        return None


class Base(DeclarativeBase):
    pass


class AccountORM(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(254))
    hashed_password: Mapped[bytes] = mapped_column(LargeBinary)
    role: Mapped[str] = mapped_column(String(16))


# case-insensitive email uniqueness (mirrors the in-memory repository check)
Index("uq_accounts_email_lower", func.lower(AccountORM.email), unique=True)


class UserORM(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    personal_group_id: Mapped[int] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(120), default="Noname")
    surname: Mapped[str] = mapped_column(String(120), default="Nosurname")
    job: Mapped[str] = mapped_column(String(255), default="Unknown job")
    rang: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(120), default="Unknown status")
    subdivision: Mapped[str] = mapped_column(String(255), default="Unknown subdivision")
    photo_url: Mapped[str] = mapped_column(String(1024), default="")


class GroupORM(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(4096), default="")
    photo_url: Mapped[str] = mapped_column(String(1024), default="")
    owner_id: Mapped[int | None] = mapped_column(default=None)


class FriendshipORM(Base):
    __tablename__ = "friendships"

    user_id: Mapped[int] = mapped_column(primary_key=True)
    friend_id: Mapped[int] = mapped_column(primary_key=True)


class SubscriptionORM(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        Index("uq_subscriptions_user_group", "user_id", "group_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(index=True)
    group_id: Mapped[int] = mapped_column(index=True)
    is_moderator: Mapped[bool] = mapped_column(default=False)


class PasteORM(Base):
    __tablename__ = "pastes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(index=True)
    author_id: Mapped[int] = mapped_column(index=True)
    text: Mapped[str] = mapped_column(String(8192))
    time: Mapped[datetime] = mapped_column(UTCDateTime)


class CommentORM(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    paste_id: Mapped[int] = mapped_column(index=True)
    author_id: Mapped[int] = mapped_column(index=True)
    text: Mapped[str] = mapped_column(String(4096))
    time: Mapped[datetime] = mapped_column(UTCDateTime)


class ChatORM(Base):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    photo_url: Mapped[str] = mapped_column(String(1024), default="")
    chat_type: Mapped[str] = mapped_column(String(16))
    owner_id: Mapped[int | None] = mapped_column(default=None)


class ChatMemberORM(Base):
    __tablename__ = "chat_members"

    chat_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(primary_key=True)
    is_owner: Mapped[bool] = mapped_column(default=False)


class MessageORM(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(index=True)
    author_id: Mapped[int] = mapped_column(index=True)
    text: Mapped[str] = mapped_column(String(8192))
    time: Mapped[datetime] = mapped_column(UTCDateTime)


class MediaORM(Base):
    __tablename__ = "media"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), default="")
    content_type: Mapped[str] = mapped_column(String(128))
    data: Mapped[bytes] = mapped_column(LargeBinary)


# --- ORM <-> domain conversion helpers ---

def account_to_domain(orm: AccountORM) -> dm.Account:
    return dm.Account(id=orm.id, email=orm.email,
                      hashed_password=orm.hashed_password, role=dm.Role(orm.role))


def user_to_domain(orm: UserORM) -> dm.User:
    return dm.User(id=orm.id, personal_group_id=orm.personal_group_id, name=orm.name,
                   surname=orm.surname, job=orm.job, rang=orm.rang, status=orm.status,
                   subdivision=orm.subdivision, photo_url=orm.photo_url)


def group_to_domain(orm: GroupORM) -> dm.Group:
    return dm.Group(id=orm.id, name=orm.name, description=orm.description,
                    photo_url=orm.photo_url, owner_id=orm.owner_id)


def subscription_to_domain(orm: SubscriptionORM) -> dm.Subscription:
    return dm.Subscription(id=orm.id, user_id=orm.user_id, group_id=orm.group_id,
                           is_moderator=orm.is_moderator)


def paste_to_domain(orm: PasteORM) -> dm.Paste:
    return dm.Paste(id=orm.id, group_id=orm.group_id, author_id=orm.author_id,
                    text=orm.text, time=orm.time)


def comment_to_domain(orm: CommentORM) -> dm.Comment:
    return dm.Comment(id=orm.id, paste_id=orm.paste_id, author_id=orm.author_id,
                      text=orm.text, time=orm.time)


def chat_to_domain(orm: ChatORM) -> dm.Chat:
    return dm.Chat(id=orm.id, name=orm.name, photo_url=orm.photo_url,
                   chat_type=dm.ChatType(orm.chat_type), owner_id=orm.owner_id)


def message_to_domain(orm: MessageORM) -> dm.Message:
    return dm.Message(id=orm.id, chat_id=orm.chat_id, author_id=orm.author_id,
                      text=orm.text, time=orm.time)


def media_to_domain(orm: MediaORM) -> dm.MediaFile:
    return dm.MediaFile(id=orm.id, filename=orm.filename,
                        content_type=orm.content_type, data=orm.data)
