"""Pydantic DTOs for /media endpoints."""

from pydantic import BaseModel


class MediaDTO(BaseModel):
    photo_url: str
