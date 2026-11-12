"""Pydantic DTOs for /users endpoints (request/response boundary models)."""

from typing import Literal, Optional

from pydantic import BaseModel

from app.domains import models as dm


class UserListItemDTO(BaseModel):
    id: int
    personal_group_id: int
    name: str
    surname: str
    photo_url: str

    @classmethod
    def from_entity(cls, user: dm.UserListItem) -> "UserListItemDTO":
        return cls(
            id=user.id,
            personal_group_id=user.personal_group_id,
            name=user.name,
            surname=user.surname,
            photo_url=user.photo_url,
        )


class UserDTO(BaseModel):
    id: int
    name: str
    surname: str
    job: str
    rang: int
    status: str
    subdivision: str
    photo_url: str

    @classmethod
    def from_entity(cls, user: dm.User) -> "UserDTO":
        return cls(
            id=user.id,
            name=user.name,
            surname=user.surname,
            job=user.job,
            rang=user.rang,
            status=user.status,
            subdivision=user.subdivision,
            photo_url=user.photo_url,
        )


class UserPatchDTO(BaseModel):
    """All fields optional; fields not present in the request are ignored
    (merge-patch semantics). JSON null is treated the same as absent."""

    name: Optional[str] = None
    surname: Optional[str] = None
    job: Optional[str] = None
    rang: Optional[int] = None
    status: Optional[str] = None
    subdivision: Optional[str] = None
    photo_url: Optional[str] = None

    def to_entity(self) -> dm.UserPatch:
        provided = self.model_fields_set
        return dm.UserPatch(
            name=self.name if "name" in provided else None,
            surname=self.surname if "surname" in provided else None,
            job=self.job if "job" in provided else None,
            rang=self.rang if "rang" in provided else None,
            status=self.status if "status" in provided else None,
            subdivision=self.subdivision if "subdivision" in provided else None,
            photo_url=self.photo_url if "photo_url" in provided else None,
        )


class FriendListItemDTO(BaseModel):
    id: int
    name: str
    surname: str
    photo_url: str

    @classmethod
    def from_entity(cls, friend: dm.FriendListItem) -> "FriendListItemDTO":
        return cls(
            id=friend.id,
            name=friend.name,
            surname=friend.surname,
            photo_url=friend.photo_url,
        )


class FriendPostDTO(BaseModel):
    """The user to add as a friend. (The spec's requestBody references a
    `Friend` schema that does not exist; `FriendPost` is the intended one.)"""

    user_id: int


class SubscriptionPostDTO(BaseModel):
    group_id: int
    is_moderator: bool = False

    def to_entity(self, user_id: int) -> dm.Subscription:
        return dm.Subscription(id=0, user_id=user_id, group_id=self.group_id,
                               is_moderator=self.is_moderator)


class SubscriptionListItemDTO(BaseModel):
    # `id` added on top of the spec schema: DELETE
    # /users/{UserID}/subscriptions/{SubscriptionID} needs it.
    id: int
    sub_type: Literal["group", "user"]
    group_id: int
    user_id: int = -1
    name: str
    is_moderator: bool = False
    photo_url: str = ""

    @classmethod
    def from_entity(cls, item: dm.SubscriptionListItem) -> "SubscriptionListItemDTO":
        return cls(
            id=item.id,
            sub_type=item.sub_type.value,
            group_id=item.group_id,
            user_id=item.user_id,
            name=item.name,
            is_moderator=item.is_moderator,
            photo_url=item.photo_url,
        )
