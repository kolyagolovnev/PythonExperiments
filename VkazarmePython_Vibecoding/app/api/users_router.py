"""/users endpoints: profiles, search, friends, subscriptions."""

from typing import Annotated, Optional

from fastapi import APIRouter, Body, Depends, Path, Query

from app.api.deps import get_current_token, get_user_service
from app.domains import models as dm
from app.dto.user_dto import (
    FriendListItemDTO,
    FriendPostDTO,
    SubscriptionListItemDTO,
    SubscriptionPostDTO,
    UserDTO,
    UserListItemDTO,
    UserPatchDTO,
)
from app.services.user_service import UserService

router = APIRouter(tags=["users"])

Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


@router.get("/users", response_model=list[UserListItemDTO])
async def search_users(
    name: Optional[str] = Query(default=None, description="User's first name"),
    surname: Optional[str] = Query(default=None, description="User's last name"),
    limit: Limit = 10,
    offset: Offset = 0,
    token: dm.AuthToken = Depends(get_current_token),
    user_service: UserService = Depends(get_user_service),
) -> list[UserListItemDTO]:
    params = dm.UserSearchParams(name=name, surname=surname, limit=limit, offset=offset)
    found = await user_service.search_users(params)
    return [UserListItemDTO.from_entity(user) for user in found]


@router.get("/users/{UserID}", response_model=UserDTO)
async def get_user(
    user_id: Annotated[int, Path(alias="UserID")],
    token: dm.AuthToken = Depends(get_current_token),
    user_service: UserService = Depends(get_user_service),
) -> UserDTO:
    user = await user_service.get_user(user_id)
    return UserDTO.from_entity(user)


@router.patch("/users/{UserID}", status_code=200)
async def patch_user(
    user_id: Annotated[int, Path(alias="UserID")],
    body: UserPatchDTO = Body(media_type="application/merge-patch+json"),
    token: dm.AuthToken = Depends(get_current_token),
    user_service: UserService = Depends(get_user_service),
) -> None:
    await user_service.patch_user(token, user_id, body.to_entity())


@router.delete("/users/{UserID}", status_code=200)
async def delete_user(
    user_id: Annotated[int, Path(alias="UserID")],
    token: dm.AuthToken = Depends(get_current_token),
    user_service: UserService = Depends(get_user_service),
) -> None:
    await user_service.delete_user(token, user_id)


@router.get("/users/{UserID}/friends", response_model=list[FriendListItemDTO])
async def list_friends(
    user_id: Annotated[int, Path(alias="UserID")],
    name: Optional[str] = Query(default=None, description="User's first name"),
    surname: Optional[str] = Query(default=None, description="User's last name"),
    limit: Limit = 10,
    offset: Offset = 0,
    token: dm.AuthToken = Depends(get_current_token),
    user_service: UserService = Depends(get_user_service),
) -> list[FriendListItemDTO]:
    params = dm.UserSearchParams(name=name, surname=surname, limit=limit, offset=offset)
    friends = await user_service.list_friends(user_id, params)
    return [FriendListItemDTO.from_entity(friend) for friend in friends]


@router.post("/users/{UserID}/friends", status_code=200)
async def add_friend(
    user_id: Annotated[int, Path(alias="UserID")],
    body: FriendPostDTO,
    token: dm.AuthToken = Depends(get_current_token),
    user_service: UserService = Depends(get_user_service),
) -> None:
    await user_service.add_friend(token, user_id, body.user_id)


@router.delete("/users/{UserID}/friends/{FriendID}", status_code=200)
async def remove_friend(
    user_id: Annotated[int, Path(alias="UserID")],
    friend_id: Annotated[int, Path(alias="FriendID")],
    token: dm.AuthToken = Depends(get_current_token),
    user_service: UserService = Depends(get_user_service),
) -> None:
    await user_service.remove_friend(token, user_id, friend_id)


@router.get("/users/{UserID}/subscriptions", response_model=list[SubscriptionListItemDTO])
async def list_subscriptions(
    user_id: Annotated[int, Path(alias="UserID")],
    limit: Limit = 10,
    offset: Offset = 0,
    token: dm.AuthToken = Depends(get_current_token),
    user_service: UserService = Depends(get_user_service),
) -> list[SubscriptionListItemDTO]:
    items = await user_service.list_subscriptions(user_id, limit=limit, offset=offset)
    return [SubscriptionListItemDTO.from_entity(item) for item in items]


@router.post("/users/{UserID}/subscriptions", status_code=200)
async def subscribe(
    user_id: Annotated[int, Path(alias="UserID")],
    body: SubscriptionPostDTO,
    token: dm.AuthToken = Depends(get_current_token),
    user_service: UserService = Depends(get_user_service),
) -> None:
    subscription = body.to_entity(user_id)
    await user_service.subscribe(token, user_id, subscription)


@router.delete("/users/{UserID}/subscriptions/{SubscriptionID}", status_code=200)
async def unsubscribe(
    user_id: Annotated[int, Path(alias="UserID")],
    subscription_id: Annotated[int, Path(alias="SubscriptionID")],
    token: dm.AuthToken = Depends(get_current_token),
    user_service: UserService = Depends(get_user_service),
) -> None:
    await user_service.unsubscribe(token, user_id, subscription_id)
