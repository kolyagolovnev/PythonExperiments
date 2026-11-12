"""Groups: search, profile, admin CRUD and deletion cascade.

- POST/PATCH/DELETE /groups are admin-only (the spec's x-required-role).
  A moderator may NOT patch the group description (spec is explicit).
- Deleting a group cascades its pastes, the pastes' comments and every
  subscription pointing at it. UserService reuses this cascade when an
  admin deletes a user (whose personal group then disappears too).
"""

from typing import Optional

from app.domains import models as dm
from app.repositories.interfaces import (
    CommentRepository,
    GroupRepository,
    PasteRepository,
    SubscriptionRepository,
)
from app.services.exceptions import PermissionDenied


class GroupService:
    def __init__(
        self,
        group_repo: GroupRepository,
        paste_repo: PasteRepository,
        comment_repo: CommentRepository,
        subscription_repo: SubscriptionRepository,
    ):
        self._group_repo = group_repo
        self._paste_repo = paste_repo
        self._comment_repo = comment_repo
        self._subscription_repo = subscription_repo

    async def search_groups(self, name: Optional[str], limit: int,
                            offset: int) -> list[dm.GroupListItem]:
        return await self._group_repo.search(name, limit, offset)

    async def get_group(self, group_id: int) -> dm.Group:
        return await self._group_repo.get(group_id)

    async def create_group(self, requester: dm.AuthToken, data: dm.GroupPost) -> dm.Group:
        if requester.role != dm.Role.ADMIN:
            raise PermissionDenied()
        return await self._group_repo.add(
            dm.Group(id=0, name=data.name, description=data.description,
                     photo_url=data.photo_url)
        )

    async def patch_group(self, requester: dm.AuthToken, group_id: int,
                          patch: dm.GroupPatch) -> dm.Group:
        if requester.role != dm.Role.ADMIN:
            raise PermissionDenied()
        group = await self._group_repo.get(group_id)
        for field_name, value in vars(patch).items():
            if value is not None:
                setattr(group, field_name, value)
        return await self._group_repo.update(group)

    async def delete_group(self, requester: Optional[dm.AuthToken], group_id: int) -> None:
        # requester=None means an internal cascade (admin deleting a user
        # removes the user's personal group without an admin token at hand).
        if requester is not None and requester.role != dm.Role.ADMIN:
            raise PermissionDenied()
        await self._group_repo.get(group_id)  # GroupNotFound -> 404
        paste_ids = await self._paste_repo.paste_ids_for_group(group_id)
        await self._comment_repo.remove_all_for_pastes(paste_ids)
        await self._paste_repo.remove_all_for_group(group_id)
        await self._subscription_repo.remove_all_for_group(group_id)
        await self._group_repo.delete(group_id)
