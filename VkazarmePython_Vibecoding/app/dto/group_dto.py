"""Pydantic DTOs for /groups endpoints (groups, pastes, comments)."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.domains import models as dm
from app.dto.user_dto import UserListItemDTO


class GroupListItemDTO(BaseModel):
    id: int
    name: str
    photo_url: str

    @classmethod
    def from_entity(cls, group: dm.GroupListItem) -> "GroupListItemDTO":
        return cls(id=group.id, name=group.name, photo_url=group.photo_url)


class GroupDTO(BaseModel):
    id: int
    name: str
    description: str
    photo_url: str

    @classmethod
    def from_entity(cls, group: dm.Group) -> "GroupDTO":
        return cls(id=group.id, name=group.name, description=group.description,
                   photo_url=group.photo_url)


class GroupPostDTO(BaseModel):
    """Body of POST /groups. The spec references the `Group` schema (whose id
    is server-assigned), so only the writable fields are accepted here."""

    name: str
    description: str = ""
    photo_url: str = ""

    def to_entity(self) -> dm.GroupPost:
        return dm.GroupPost(name=self.name, description=self.description,
                            photo_url=self.photo_url)


class GroupPatchDTO(BaseModel):
    """All fields optional; fields not present in the request are ignored
    (merge-patch semantics). JSON null is treated the same as absent."""

    name: Optional[str] = None
    description: Optional[str] = None
    photo_url: Optional[str] = None

    def to_entity(self) -> dm.GroupPatch:
        provided = self.model_fields_set
        return dm.GroupPatch(
            name=self.name if "name" in provided else None,
            description=self.description if "description" in provided else None,
            photo_url=self.photo_url if "photo_url" in provided else None,
        )


class PasteDTO(BaseModel):
    id: int
    group_id: int
    text: str
    time: datetime

    @classmethod
    def from_entity(cls, paste: dm.Paste) -> "PasteDTO":
        return cls(id=paste.id, group_id=paste.group_id, text=paste.text, time=paste.time)


class PastePostDTO(BaseModel):
    """Body of POST /groups/{GroupID}/pastes. The spec references a
    `PastePost` schema that is not defined in components; the group and the
    author come from the path/token, so only the text is accepted."""

    text: str = Field(min_length=1)


class CommentDTO(BaseModel):
    id: int
    paste_id: int
    text: str
    time: datetime
    author: UserListItemDTO

    @classmethod
    def from_entity(cls, comment: dm.CommentListItem) -> "CommentDTO":
        return cls(
            id=comment.id,
            paste_id=comment.paste_id,
            text=comment.text,
            time=comment.time,
            author=UserListItemDTO.from_entity(comment.author),
        )


class CommentPostDTO(BaseModel):
    """Body of POST .../comments. The spec references the `Comment` schema,
    whose id/time/author are server-side; only the text is accepted."""

    text: str = Field(min_length=1)
