"""SQLAlchemy implementations of every repository interface.

Each method runs in its own short transaction (begin/commit or rollback);
this mirrors the in-memory implementations method-for-method. Known
simplification: multi-step service cascades (e.g. group deletion) are not
one atomic transaction — hardening that with a unit of work is future work.

Uniqueness violations surface as sqlalchemy.exc.IntegrityError and are
translated into the same repository exceptions the in-memory layer raises
(so the HTTP mapping in app/main.py is unchanged).
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

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
from app.repositories.sqlalchemy_repos import orm
from app.repositories.sqlalchemy_repos.engine import build_sessionmaker


class SQLAlchemyAccountRepository(AccountRepository):
    def __init__(self, sessionmaker: async_sessionmaker):
        self._sessionmaker = sessionmaker

    async def add(self, account: dm.Account) -> dm.Account:
        async with self._sessionmaker() as session, session.begin():
            orm_account = orm.AccountORM(
                email=account.email,
                hashed_password=account.hashed_password,
                role=account.role.value,
            )
            session.add(orm_account)
            try:
                await session.flush()
            except IntegrityError as error:
                raise rex.EmailAlreadyExists() from error
            return orm.account_to_domain(orm_account)

    async def find_by_email(self, email: str) -> Optional[dm.Account]:
        async with self._sessionmaker() as session:
            result = await session.execute(
                select(orm.AccountORM).where(
                    func.lower(orm.AccountORM.email) == email.lower()
                )
            )
            found = result.scalar_one_or_none()
            return orm.account_to_domain(found) if found else None

    async def get(self, account_id: int) -> dm.Account:
        async with self._sessionmaker() as session:
            found = await session.get(orm.AccountORM, account_id)
            if found is None:
                raise rex.AccountNotFound()
            return orm.account_to_domain(found)

    async def delete(self, account_id: int) -> None:
        async with self._sessionmaker() as session, session.begin():
            found = await session.get(orm.AccountORM, account_id)
            if found is None:
                raise rex.AccountNotFound()
            await session.delete(found)


class SQLAlchemyUserRepository(UserRepository):
    def __init__(self, sessionmaker: async_sessionmaker):
        self._sessionmaker = sessionmaker

    async def add(self, user: dm.User) -> dm.User:
        async with self._sessionmaker() as session, session.begin():
            session.add(orm.UserORM(
                id=user.id,
                personal_group_id=user.personal_group_id,
                name=user.name,
                surname=user.surname,
                job=user.job,
                rang=user.rang,
                status=user.status,
                subdivision=user.subdivision,
                photo_url=user.photo_url,
            ))
            return user

    async def get(self, user_id: int) -> dm.User:
        async with self._sessionmaker() as session:
            found = await session.get(orm.UserORM, user_id)
            if found is None:
                raise rex.UserNotFound()
            return orm.user_to_domain(found)

    async def update(self, user: dm.User) -> dm.User:
        async with self._sessionmaker() as session, session.begin():
            found = await session.get(orm.UserORM, user.id)
            if found is None:
                raise rex.UserNotFound()
            found.name = user.name
            found.surname = user.surname
            found.job = user.job
            found.rang = user.rang
            found.status = user.status
            found.subdivision = user.subdivision
            found.photo_url = user.photo_url
            return user

    async def delete(self, user_id: int) -> None:
        async with self._sessionmaker() as session, session.begin():
            found = await session.get(orm.UserORM, user_id)
            if found is None:
                raise rex.UserNotFound()
            await session.delete(found)

    async def search(self, params: dm.UserSearchParams) -> list[dm.UserListItem]:
        name = (params.name or "").lower()
        surname = (params.surname or "").lower()
        async with self._sessionmaker() as session:
            query = select(orm.UserORM).order_by(orm.UserORM.id)
            if name:
                query = query.where(func.lower(orm.UserORM.name).like(f"%{name}%"))
            if surname:
                query = query.where(func.lower(orm.UserORM.surname).like(f"%{surname}%"))
            query = query.offset(params.offset).limit(params.limit)
            rows = (await session.execute(query)).scalars().all()
            return [
                dm.UserListItem(id=row.id, personal_group_id=row.personal_group_id,
                                name=row.name, surname=row.surname, photo_url=row.photo_url)
                for row in rows
            ]


class SQLAlchemyGroupRepository(GroupRepository):
    def __init__(self, sessionmaker: async_sessionmaker):
        self._sessionmaker = sessionmaker

    async def add(self, group: dm.Group) -> dm.Group:
        async with self._sessionmaker() as session, session.begin():
            orm_group = orm.GroupORM(
                name=group.name, description=group.description,
                photo_url=group.photo_url, owner_id=group.owner_id,
            )
            session.add(orm_group)
            await session.flush()
            return orm.group_to_domain(orm_group)

    async def get(self, group_id: int) -> dm.Group:
        async with self._sessionmaker() as session:
            found = await session.get(orm.GroupORM, group_id)
            if found is None:
                raise rex.GroupNotFound()
            return orm.group_to_domain(found)

    async def update(self, group: dm.Group) -> dm.Group:
        async with self._sessionmaker() as session, session.begin():
            found = await session.get(orm.GroupORM, group.id)
            if found is None:
                raise rex.GroupNotFound()
            found.name = group.name
            found.description = group.description
            found.photo_url = group.photo_url
            return group

    async def delete(self, group_id: int) -> None:
        async with self._sessionmaker() as session, session.begin():
            found = await session.get(orm.GroupORM, group_id)
            if found is None:
                raise rex.GroupNotFound()
            await session.delete(found)

    async def search(self, name: str | None, limit: int, offset: int) -> list[dm.GroupListItem]:
        async with self._sessionmaker() as session:
            query = (
                select(orm.GroupORM)
                .where(orm.GroupORM.owner_id.is_(None))  # topic groups only
                .order_by(orm.GroupORM.id)
                .offset(offset)
                .limit(limit)
            )
            if name:
                query = query.where(func.lower(orm.GroupORM.name).like(f"%{name.lower()}%"))
            rows = (await session.execute(query)).scalars().all()
            return [dm.GroupListItem(id=row.id, name=row.name, photo_url=row.photo_url)
                    for row in rows]


class SQLAlchemyFriendRepository(FriendRepository):
    def __init__(self, sessionmaker: async_sessionmaker, user_repo: UserRepository):
        self._sessionmaker = sessionmaker
        self._user_repo = user_repo

    async def add(self, user_id: int, friend_id: int) -> None:
        async with self._sessionmaker() as session, session.begin():
            existing = await session.execute(
                select(orm.FriendshipORM).where(
                    orm.FriendshipORM.user_id == user_id,
                    orm.FriendshipORM.friend_id == friend_id,
                )
            )
            if existing.scalar_one_or_none() is not None:
                raise rex.AlreadyFriends()
            session.add(orm.FriendshipORM(user_id=user_id, friend_id=friend_id))
            session.add(orm.FriendshipORM(user_id=friend_id, friend_id=user_id))

    async def remove(self, user_id: int, friend_id: int) -> None:
        async with self._sessionmaker() as session, session.begin():
            result = await session.execute(
                delete(orm.FriendshipORM).where(
                    orm.FriendshipORM.user_id == user_id,
                    orm.FriendshipORM.friend_id == friend_id,
                )
            )
            if result.rowcount == 0:
                raise rex.FriendshipNotFound()
            await session.execute(
                delete(orm.FriendshipORM).where(
                    orm.FriendshipORM.user_id == friend_id,
                    orm.FriendshipORM.friend_id == user_id,
                )
            )

    async def list_friends(self, user_id: int,
                           params: dm.UserSearchParams) -> list[dm.FriendListItem]:
        name = (params.name or "").lower()
        surname = (params.surname or "").lower()
        async with self._sessionmaker() as session:
            query = (
                select(orm.FriendshipORM.friend_id, orm.UserORM)
                .join(orm.UserORM, orm.UserORM.id == orm.FriendshipORM.friend_id)
                .where(orm.FriendshipORM.user_id == user_id)
                .order_by(orm.FriendshipORM.friend_id)
            )
            if name:
                query = query.where(func.lower(orm.UserORM.name).like(f"%{name}%"))
            if surname:
                query = query.where(func.lower(orm.UserORM.surname).like(f"%{surname}%"))
            query = query.offset(params.offset).limit(params.limit)
            rows = (await session.execute(query)).all()
            return [
                dm.FriendListItem(id=user_orm.id, name=user_orm.name,
                                  surname=user_orm.surname, photo_url=user_orm.photo_url)
                for _, user_orm in rows
            ]

    async def exists(self, user_id: int, friend_id: int) -> bool:
        async with self._sessionmaker() as session:
            result = await session.execute(
                select(orm.FriendshipORM.user_id).where(
                    orm.FriendshipORM.user_id == user_id,
                    orm.FriendshipORM.friend_id == friend_id,
                )
            )
            return result.scalar_one_or_none() is not None

    async def remove_all_for_user(self, user_id: int) -> None:
        async with self._sessionmaker() as session, session.begin():
            await session.execute(
                delete(orm.FriendshipORM).where(
                    (orm.FriendshipORM.user_id == user_id)
                    | (orm.FriendshipORM.friend_id == user_id)
                )
            )


class SQLAlchemySubscriptionRepository(SubscriptionRepository):
    def __init__(self, sessionmaker: async_sessionmaker):
        self._sessionmaker = sessionmaker

    async def add(self, subscription: dm.Subscription) -> dm.Subscription:
        async with self._sessionmaker() as session, session.begin():
            orm_subscription = orm.SubscriptionORM(
                user_id=subscription.user_id,
                group_id=subscription.group_id,
                is_moderator=subscription.is_moderator,
            )
            session.add(orm_subscription)
            try:
                await session.flush()
            except IntegrityError as error:
                raise rex.AlreadySubscribed() from error
            return orm.subscription_to_domain(orm_subscription)

    async def remove(self, user_id: int, subscription_id: int) -> None:
        async with self._sessionmaker() as session, session.begin():
            found = await session.get(orm.SubscriptionORM, subscription_id)
            if found is None or found.user_id != user_id:
                raise rex.SubscriptionNotFound()
            await session.delete(found)

    async def get(self, subscription_id: int) -> dm.Subscription:
        async with self._sessionmaker() as session:
            found = await session.get(orm.SubscriptionORM, subscription_id)
            if found is None:
                raise rex.SubscriptionNotFound()
            return orm.subscription_to_domain(found)

    async def find_for_user_group(self, user_id: int, group_id: int) -> Optional[dm.Subscription]:
        async with self._sessionmaker() as session:
            result = await session.execute(
                select(orm.SubscriptionORM).where(
                    orm.SubscriptionORM.user_id == user_id,
                    orm.SubscriptionORM.group_id == group_id,
                )
            )
            found = result.scalar_one_or_none()
            return orm.subscription_to_domain(found) if found else None

    async def list_for_user(self, user_id: int, limit: int, offset: int) -> list[dm.Subscription]:
        async with self._sessionmaker() as session:
            query = (
                select(orm.SubscriptionORM)
                .where(orm.SubscriptionORM.user_id == user_id)
                .order_by(orm.SubscriptionORM.id)
                .offset(offset)
                .limit(limit)
            )
            rows = (await session.execute(query)).scalars().all()
            return [orm.subscription_to_domain(row) for row in rows]

    async def remove_all_for_user(self, user_id: int) -> None:
        async with self._sessionmaker() as session, session.begin():
            await session.execute(
                delete(orm.SubscriptionORM).where(orm.SubscriptionORM.user_id == user_id)
            )

    async def remove_all_for_group(self, group_id: int) -> None:
        async with self._sessionmaker() as session, session.begin():
            await session.execute(
                delete(orm.SubscriptionORM).where(orm.SubscriptionORM.group_id == group_id)
            )


class SQLAlchemyPasteRepository(PasteRepository):
    def __init__(self, sessionmaker: async_sessionmaker):
        self._sessionmaker = sessionmaker

    async def add(self, paste: dm.Paste) -> dm.Paste:
        async with self._sessionmaker() as session, session.begin():
            orm_paste = orm.PasteORM(
                group_id=paste.group_id, author_id=paste.author_id,
                text=paste.text, time=paste.time,
            )
            session.add(orm_paste)
            await session.flush()
            return orm.paste_to_domain(orm_paste)

    async def get(self, paste_id: int) -> dm.Paste:
        async with self._sessionmaker() as session:
            found = await session.get(orm.PasteORM, paste_id)
            if found is None:
                raise rex.PasteNotFound()
            return orm.paste_to_domain(found)

    async def delete(self, paste_id: int) -> None:
        async with self._sessionmaker() as session, session.begin():
            found = await session.get(orm.PasteORM, paste_id)
            if found is None:
                raise rex.PasteNotFound()
            await session.delete(found)

    async def list_for_group(self, group_id: int, limit: int, offset: int) -> list[dm.Paste]:
        async with self._sessionmaker() as session:
            query = (
                select(orm.PasteORM)
                .where(orm.PasteORM.group_id == group_id)
                .order_by(orm.PasteORM.id)
                .offset(offset)
                .limit(limit)
            )
            rows = (await session.execute(query)).scalars().all()
            return [orm.paste_to_domain(row) for row in rows]

    async def paste_ids_for_group(self, group_id: int) -> list[int]:
        async with self._sessionmaker() as session:
            query = select(orm.PasteORM.id).where(orm.PasteORM.group_id == group_id)
            return list((await session.execute(query)).scalars())

    async def remove_all_for_group(self, group_id: int) -> None:
        async with self._sessionmaker() as session, session.begin():
            await session.execute(
                delete(orm.PasteORM).where(orm.PasteORM.group_id == group_id)
            )


class SQLAlchemyCommentRepository(CommentRepository):
    def __init__(self, sessionmaker: async_sessionmaker):
        self._sessionmaker = sessionmaker

    async def add(self, comment: dm.Comment) -> dm.Comment:
        async with self._sessionmaker() as session, session.begin():
            orm_comment = orm.CommentORM(
                paste_id=comment.paste_id, author_id=comment.author_id,
                text=comment.text, time=comment.time,
            )
            session.add(orm_comment)
            await session.flush()
            return orm.comment_to_domain(orm_comment)

    async def list_for_paste(self, paste_id: int, limit: int, offset: int) -> list[dm.Comment]:
        async with self._sessionmaker() as session:
            query = (
                select(orm.CommentORM)
                .where(orm.CommentORM.paste_id == paste_id)
                .order_by(orm.CommentORM.id)
                .offset(offset)
                .limit(limit)
            )
            rows = (await session.execute(query)).scalars().all()
            return [orm.comment_to_domain(row) for row in rows]

    async def remove_all_for_pastes(self, paste_ids: list[int]) -> None:
        if not paste_ids:
            return
        async with self._sessionmaker() as session, session.begin():
            await session.execute(
                delete(orm.CommentORM).where(orm.CommentORM.paste_id.in_(paste_ids))
            )


class SQLAlchemyChatMemberRepository(ChatMemberRepository):
    def __init__(self, sessionmaker: async_sessionmaker):
        self._sessionmaker = sessionmaker

    async def add(self, member: dm.ChatMember) -> None:
        async with self._sessionmaker() as session, session.begin():
            session.add(orm.ChatMemberORM(
                chat_id=member.chat_id, user_id=member.user_id,
                is_owner=member.is_owner,
            ))
            try:
                await session.flush()
            except IntegrityError as error:
                raise rex.AlreadyMember() from error

    async def remove(self, chat_id: int, user_id: int) -> None:
        async with self._sessionmaker() as session, session.begin():
            result = await session.execute(
                delete(orm.ChatMemberORM).where(
                    orm.ChatMemberORM.chat_id == chat_id,
                    orm.ChatMemberORM.user_id == user_id,
                )
            )
            if result.rowcount == 0:
                raise rex.ChatMemberNotFound()

    async def is_member(self, chat_id: int, user_id: int) -> bool:
        async with self._sessionmaker() as session:
            result = await session.execute(
                select(orm.ChatMemberORM.user_id).where(
                    orm.ChatMemberORM.chat_id == chat_id,
                    orm.ChatMemberORM.user_id == user_id,
                )
            )
            return result.scalar_one_or_none() is not None

    async def get(self, chat_id: int, user_id: int) -> dm.ChatMember:
        async with self._sessionmaker() as session:
            found = await session.get(orm.ChatMemberORM, (chat_id, user_id))
            if found is None:
                raise rex.ChatMemberNotFound()
            return dm.ChatMember(chat_id=found.chat_id, user_id=found.user_id,
                                 is_owner=found.is_owner)

    async def list_for_chat(self, chat_id: int, limit: int, offset: int) -> list[dm.ChatMember]:
        async with self._sessionmaker() as session:
            query = (
                select(orm.ChatMemberORM)
                .where(orm.ChatMemberORM.chat_id == chat_id)
                .order_by(orm.ChatMemberORM.user_id)
                .offset(offset)
                .limit(limit)
            )
            rows = (await session.execute(query)).scalars().all()
            return [dm.ChatMember(chat_id=row.chat_id, user_id=row.user_id,
                                  is_owner=row.is_owner) for row in rows]

    async def chat_ids_for_user(self, user_id: int) -> list[int]:
        async with self._sessionmaker() as session:
            query = (
                select(orm.ChatMemberORM.chat_id)
                .where(orm.ChatMemberORM.user_id == user_id)
                .order_by(orm.ChatMemberORM.chat_id)
            )
            return list((await session.execute(query)).scalars())

    async def user_ids_for_chat(self, chat_id: int) -> list[int]:
        async with self._sessionmaker() as session:
            query = (
                select(orm.ChatMemberORM.user_id)
                .where(orm.ChatMemberORM.chat_id == chat_id)
                .order_by(orm.ChatMemberORM.user_id)
            )
            return list((await session.execute(query)).scalars())

    async def remove_all_for_chat(self, chat_id: int) -> None:
        async with self._sessionmaker() as session, session.begin():
            await session.execute(
                delete(orm.ChatMemberORM).where(orm.ChatMemberORM.chat_id == chat_id)
            )

    async def remove_user_from_chat(self, chat_id: int, user_id: int) -> None:
        async with self._sessionmaker() as session, session.begin():
            await session.execute(
                delete(orm.ChatMemberORM).where(
                    orm.ChatMemberORM.chat_id == chat_id,
                    orm.ChatMemberORM.user_id == user_id,
                )
            )


class SQLAlchemyChatRepository(ChatRepository):
    def __init__(self, sessionmaker: async_sessionmaker,
                 member_repo: ChatMemberRepository):
        self._sessionmaker = sessionmaker
        self._member_repo = member_repo

    async def add(self, chat: dm.Chat) -> dm.Chat:
        async with self._sessionmaker() as session, session.begin():
            orm_chat = orm.ChatORM(
                name=chat.name, photo_url=chat.photo_url,
                chat_type=chat.chat_type.value, owner_id=chat.owner_id,
            )
            session.add(orm_chat)
            await session.flush()
            return orm.chat_to_domain(orm_chat)

    async def get(self, chat_id: int) -> dm.Chat:
        async with self._sessionmaker() as session:
            found = await session.get(orm.ChatORM, chat_id)
            if found is None:
                raise rex.ChatNotFound()
            return orm.chat_to_domain(found)

    async def delete(self, chat_id: int) -> None:
        async with self._sessionmaker() as session, session.begin():
            await session.execute(delete(orm.ChatORM).where(orm.ChatORM.id == chat_id))

    async def list_for_user(self, user_id: int, limit: int, offset: int) -> list[dm.Chat]:
        chat_ids = await self._member_repo.chat_ids_for_user(user_id)
        window = chat_ids[offset:offset + limit]
        return [await self.get(chat_id) for chat_id in window]

    async def find_personal_chat(self, user_a: int, user_b: int) -> Optional[dm.Chat]:
        async with self._sessionmaker() as session:
            query = (
                select(orm.ChatORM)
                .where(orm.ChatORM.chat_type == dm.ChatType.PERSONAL.value)
            )
            chats = (await session.execute(query)).scalars().all()
        for chat in chats:
            members = await self._member_repo.user_ids_for_chat(chat.id)
            if len(members) == 2 and user_a in members and user_b in members:
                return orm.chat_to_domain(chat)
        return None


class SQLAlchemyMessageRepository(MessageRepository):
    def __init__(self, sessionmaker: async_sessionmaker):
        self._sessionmaker = sessionmaker

    async def add(self, message: dm.Message) -> dm.Message:
        async with self._sessionmaker() as session, session.begin():
            orm_message = orm.MessageORM(
                chat_id=message.chat_id, author_id=message.author_id,
                text=message.text, time=message.time,
            )
            session.add(orm_message)
            await session.flush()
            return orm.message_to_domain(orm_message)

    async def list_for_chat(self, chat_id: int, limit: int, offset: int) -> list[dm.Message]:
        async with self._sessionmaker() as session:
            query = (
                select(orm.MessageORM)
                .where(orm.MessageORM.chat_id == chat_id)
                .order_by(orm.MessageORM.id)
                .offset(offset)
                .limit(limit)
            )
            rows = (await session.execute(query)).scalars().all()
            return [orm.message_to_domain(row) for row in rows]

    async def remove_all_for_chat(self, chat_id: int) -> None:
        async with self._sessionmaker() as session, session.begin():
            await session.execute(
                delete(orm.MessageORM).where(orm.MessageORM.chat_id == chat_id)
            )


class SQLAlchemyMediaRepository(MediaRepository):
    def __init__(self, sessionmaker: async_sessionmaker):
        self._sessionmaker = sessionmaker

    async def add(self, media: dm.MediaFile) -> dm.MediaFile:
        async with self._sessionmaker() as session, session.begin():
            orm_media = orm.MediaORM(
                filename=media.filename, content_type=media.content_type,
                data=media.data,
            )
            session.add(orm_media)
            await session.flush()
            return orm.media_to_domain(orm_media)

    async def get(self, media_id: int) -> dm.MediaFile:
        async with self._sessionmaker() as session:
            found = await session.get(orm.MediaORM, media_id)
            if found is None:
                raise rex.MediaNotFound()
            return orm.media_to_domain(found)


def build_sqlalchemy_repos(database_url: str) -> dict:
    """Builds every repository implementation on top of one sessionmaker."""
    sessionmaker = build_sessionmaker(database_url)
    account_repo = SQLAlchemyAccountRepository(sessionmaker)
    user_repo = SQLAlchemyUserRepository(sessionmaker)
    group_repo = SQLAlchemyGroupRepository(sessionmaker)
    friend_repo = SQLAlchemyFriendRepository(sessionmaker, user_repo)
    subscription_repo = SQLAlchemySubscriptionRepository(sessionmaker)
    paste_repo = SQLAlchemyPasteRepository(sessionmaker)
    comment_repo = SQLAlchemyCommentRepository(sessionmaker)
    chat_member_repo = SQLAlchemyChatMemberRepository(sessionmaker)
    chat_repo = SQLAlchemyChatRepository(sessionmaker, chat_member_repo)
    message_repo = SQLAlchemyMessageRepository(sessionmaker)
    media_repo = SQLAlchemyMediaRepository(sessionmaker)
    return {
        "sessionmaker": sessionmaker,
        "account_repo": account_repo,
        "user_repo": user_repo,
        "group_repo": group_repo,
        "friend_repo": friend_repo,
        "subscription_repo": subscription_repo,
        "paste_repo": paste_repo,
        "comment_repo": comment_repo,
        "chat_member_repo": chat_member_repo,
        "chat_repo": chat_repo,
        "message_repo": message_repo,
        "media_repo": media_repo,
    }
