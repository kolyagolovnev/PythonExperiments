"""Pastes (posts) and their comments.

Posting rules (from the spec and the commented-out x-required-role):
- a personal group accepts posts only from its owner ("posting entries
  on your profile");
- a topic group accepts posts from the admin and from the group's
  moderators (subscribers with is_moderator=True);
- comments can be left by any authenticated user;
- a paste can be deleted by the admin, by the owner of the personal
  group, or by a moderator of the group; deleting a paste drops its
  comments.
"""

from datetime import datetime, timezone

from app.domains import models as dm
from app.repositories.interfaces import (
    CommentRepository,
    GroupRepository,
    PasteRepository,
    SubscriptionRepository,
    UserRepository,
)
from app.services.exceptions import PasteNotFound, PermissionDenied


class PasteService:
    def __init__(
        self,
        paste_repo: PasteRepository,
        comment_repo: CommentRepository,
        group_repo: GroupRepository,
        subscription_repo: SubscriptionRepository,
        user_repo: UserRepository,
    ):
        self._paste_repo = paste_repo
        self._comment_repo = comment_repo
        self._group_repo = group_repo
        self._subscription_repo = subscription_repo
        self._user_repo = user_repo

    # --- pastes ---

    async def list_pastes(self, group_id: int, limit: int,
                          offset: int) -> list[dm.Paste]:
        await self._group_repo.get(group_id)  # GroupNotFound -> 404
        return await self._paste_repo.list_for_group(group_id, limit, offset)

    async def get_paste(self, group_id: int, paste_id: int) -> dm.Paste:
        await self._group_repo.get(group_id)
        paste = await self._paste_repo.get(paste_id)  # PasteNotFound -> 404
        self._ensure_paste_in_group(paste, group_id)
        return paste

    async def create_paste(self, requester: dm.AuthToken, group_id: int,
                           text: str) -> dm.Paste:
        group = await self._group_repo.get(group_id)
        await self._ensure_can_post(requester, group)
        return await self._paste_repo.add(
            dm.Paste(id=0, group_id=group_id, author_id=requester.sub,
                     text=text, time=datetime.now(timezone.utc))
        )

    async def delete_paste(self, requester: dm.AuthToken, group_id: int,
                           paste_id: int) -> None:
        group = await self._group_repo.get(group_id)
        paste = await self._paste_repo.get(paste_id)
        self._ensure_paste_in_group(paste, group_id)
        if not await self._can_delete(requester, group):
            raise PermissionDenied()
        await self._comment_repo.remove_all_for_pastes([paste_id])
        await self._paste_repo.delete(paste_id)

    # --- comments ---

    async def list_comments(self, group_id: int, paste_id: int, limit: int,
                            offset: int) -> list[dm.CommentListItem]:
        await self._get_group_paste(group_id, paste_id)
        comments = await self._comment_repo.list_for_paste(paste_id, limit, offset)
        items: list[dm.CommentListItem] = []
        for comment in comments:
            author = await self._user_repo.get(comment.author_id)
            items.append(self._to_comment_item(comment, author))
        return items

    async def add_comment(self, requester: dm.AuthToken, group_id: int,
                          paste_id: int, text: str) -> dm.CommentListItem:
        await self._get_group_paste(group_id, paste_id)
        comment = await self._comment_repo.add(
            dm.Comment(id=0, paste_id=paste_id, author_id=requester.sub,
                       text=text, time=datetime.now(timezone.utc))
        )
        author = await self._user_repo.get(comment.author_id)
        return self._to_comment_item(comment, author)

    # --- helpers ---

    async def _get_group_paste(self, group_id: int, paste_id: int) -> dm.Paste:
        await self._group_repo.get(group_id)
        paste = await self._paste_repo.get(paste_id)
        self._ensure_paste_in_group(paste, group_id)
        return paste

    @staticmethod
    def _ensure_paste_in_group(paste: dm.Paste, group_id: int) -> None:
        if paste.group_id != group_id:
            raise PasteNotFound()

    async def _ensure_can_post(self, requester: dm.AuthToken, group: dm.Group) -> None:
        if group.is_personal:
            if requester.sub != group.owner_id:
                raise PermissionDenied()
            return
        if requester.role == dm.Role.ADMIN:
            return
        subscription = await self._subscription_repo.find_for_user_group(requester.sub, group.id)
        if subscription is None or not subscription.is_moderator:
            raise PermissionDenied()

    async def _can_delete(self, requester: dm.AuthToken, group: dm.Group) -> bool:
        if requester.role == dm.Role.ADMIN:
            return True
        if group.is_personal and requester.sub == group.owner_id:
            return True
        subscription = await self._subscription_repo.find_for_user_group(requester.sub, group.id)
        return subscription is not None and subscription.is_moderator

    @staticmethod
    def _to_comment_item(comment: dm.Comment, author: dm.User) -> dm.CommentListItem:
        return dm.CommentListItem(
            id=comment.id,
            paste_id=comment.paste_id,
            text=comment.text,
            time=comment.time,
            author=dm.UserListItem(
                id=author.id,
                personal_group_id=author.personal_group_id,
                name=author.name,
                surname=author.surname,
                photo_url=author.photo_url,
            ),
        )
