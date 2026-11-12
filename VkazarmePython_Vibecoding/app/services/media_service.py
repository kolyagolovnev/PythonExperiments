"""Media upload and retrieval.

Upload rules:
- any authenticated user may upload (avatars, group photos);
- only images are accepted: image/png, image/jpeg, image/gif, image/webp;
- an empty file or a file over `media_max_bytes` is rejected (400);
- the response carries a `photo_url` pointing at `GET /media/{MediaID}`,
  which serves the stored bytes without authentication (photo URLs must
  work inside <img> tags; profile and group photos are public data).

The returned `photo_url` is attached to a profile or a group via the
existing PATCH endpoints (`photo_url` field). The in-memory storage is the
mock layer; a disk/S3 implementation replaces it behind the same interface.
"""

from app.domains import models as dm
from app.repositories.interfaces import MediaRepository
from app.services.exceptions import EmptyMediaFile, MediaTooLarge, UnsupportedMediaType
from app.settings import Settings

ALLOWED_CONTENT_TYPES = frozenset(
    {"image/png", "image/jpeg", "image/gif", "image/webp"}
)


class MediaService:
    def __init__(self, media_repo: MediaRepository, settings: Settings):
        self._media_repo = media_repo
        self._settings = settings

    async def save(self, filename: str | None, content_type: str | None,
                   data: bytes) -> str:
        if not data:
            raise EmptyMediaFile()
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise UnsupportedMediaType()
        if len(data) > self._settings.media_max_bytes:
            raise MediaTooLarge()
        media = await self._media_repo.add(
            dm.MediaFile(id=0, filename=filename or "", content_type=content_type, data=data)
        )
        return f"/media/{media.id}"

    async def get(self, media_id: int) -> dm.MediaFile:
        return await self._media_repo.get(media_id)  # MediaNotFound -> 404
