"""/groups endpoints: groups, pastes (posts) and comments."""

from typing import Annotated, Optional

from fastapi import APIRouter, Body, Depends, Path, Query

from app.api.deps import get_current_token, get_group_service, get_paste_service
from app.domains import models as dm
from app.dto.group_dto import (
    CommentDTO,
    CommentPostDTO,
    GroupDTO,
    GroupListItemDTO,
    GroupPatchDTO,
    GroupPostDTO,
    PasteDTO,
    PastePostDTO,
)
from app.services.group_service import GroupService
from app.services.paste_service import PasteService

router = APIRouter(tags=["groups"])

Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


@router.get("/groups", response_model=list[GroupListItemDTO])
async def search_groups(
    name: Optional[str] = Query(default=None, description="Group name"),
    limit: Limit = 10,
    offset: Offset = 0,
    token: dm.AuthToken = Depends(get_current_token),
    group_service: GroupService = Depends(get_group_service),
) -> list[GroupListItemDTO]:
    found = await group_service.search_groups(name, limit=limit, offset=offset)
    return [GroupListItemDTO.from_entity(group) for group in found]


@router.post("/groups", status_code=200)
async def create_group(
    body: GroupPostDTO,
    token: dm.AuthToken = Depends(get_current_token),
    group_service: GroupService = Depends(get_group_service),
) -> None:
    await group_service.create_group(token, body.to_entity())


@router.get("/groups/{GroupID}", response_model=GroupDTO)
async def get_group(
    group_id: Annotated[int, Path(alias="GroupID")],
    token: dm.AuthToken = Depends(get_current_token),
    group_service: GroupService = Depends(get_group_service),
) -> GroupDTO:
    group = await group_service.get_group(group_id)
    return GroupDTO.from_entity(group)


@router.patch("/groups/{GroupID}", status_code=200)
async def patch_group(
    group_id: Annotated[int, Path(alias="GroupID")],
    body: GroupPatchDTO = Body(media_type="application/merge-patch+json"),
    token: dm.AuthToken = Depends(get_current_token),
    group_service: GroupService = Depends(get_group_service),
) -> None:
    await group_service.patch_group(token, group_id, body.to_entity())


@router.delete("/groups/{GroupID}", status_code=200)
async def delete_group(
    group_id: Annotated[int, Path(alias="GroupID")],
    token: dm.AuthToken = Depends(get_current_token),
    group_service: GroupService = Depends(get_group_service),
) -> None:
    await group_service.delete_group(token, group_id)


@router.get("/groups/{GroupID}/pastes", response_model=list[PasteDTO])
async def list_pastes(
    group_id: Annotated[int, Path(alias="GroupID")],
    limit: Limit = 10,
    offset: Offset = 0,
    token: dm.AuthToken = Depends(get_current_token),
    paste_service: PasteService = Depends(get_paste_service),
) -> list[PasteDTO]:
    pastes = await paste_service.list_pastes(group_id, limit=limit, offset=offset)
    return [PasteDTO.from_entity(paste) for paste in pastes]


@router.post("/groups/{GroupID}/pastes", status_code=200)
async def create_paste(
    group_id: Annotated[int, Path(alias="GroupID")],
    body: PastePostDTO,
    token: dm.AuthToken = Depends(get_current_token),
    paste_service: PasteService = Depends(get_paste_service),
) -> None:
    await paste_service.create_paste(token, group_id, body.text)


@router.get("/groups/{GroupID}/pastes/{PasteID}", response_model=PasteDTO)
async def get_paste(
    group_id: Annotated[int, Path(alias="GroupID")],
    paste_id: Annotated[int, Path(alias="PasteID")],
    token: dm.AuthToken = Depends(get_current_token),
    paste_service: PasteService = Depends(get_paste_service),
) -> PasteDTO:
    paste = await paste_service.get_paste(group_id, paste_id)
    return PasteDTO.from_entity(paste)


@router.delete("/groups/{GroupID}/pastes/{PasteID}", status_code=200)
async def delete_paste(
    group_id: Annotated[int, Path(alias="GroupID")],
    paste_id: Annotated[int, Path(alias="PasteID")],
    token: dm.AuthToken = Depends(get_current_token),
    paste_service: PasteService = Depends(get_paste_service),
) -> None:
    await paste_service.delete_paste(token, group_id, paste_id)


@router.get("/groups/{GroupID}/pastes/{PasteID}/comments", response_model=list[CommentDTO])
async def list_comments(
    group_id: Annotated[int, Path(alias="GroupID")],
    paste_id: Annotated[int, Path(alias="PasteID")],
    limit: Limit = 10,
    offset: Offset = 0,
    token: dm.AuthToken = Depends(get_current_token),
    paste_service: PasteService = Depends(get_paste_service),
) -> list[CommentDTO]:
    comments = await paste_service.list_comments(group_id, paste_id, limit=limit, offset=offset)
    return [CommentDTO.from_entity(comment) for comment in comments]


@router.post("/groups/{GroupID}/pastes/{PasteID}/comments", status_code=200)
async def add_comment(
    group_id: Annotated[int, Path(alias="GroupID")],
    paste_id: Annotated[int, Path(alias="PasteID")],
    body: CommentPostDTO,
    token: dm.AuthToken = Depends(get_current_token),
    paste_service: PasteService = Depends(get_paste_service),
) -> None:
    await paste_service.add_comment(token, group_id, paste_id, body.text)
