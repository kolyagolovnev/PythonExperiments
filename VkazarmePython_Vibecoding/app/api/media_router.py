"""/media endpoints: upload and fetch stored files."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, UploadFile
from fastapi.responses import Response

from app.api.deps import get_current_token, get_media_service
from app.domains import models as dm
from app.dto.media_dto import MediaDTO
from app.services.media_service import MediaService

router = APIRouter(tags=["media"])


@router.post("/media", response_model=MediaDTO)
async def upload_media(
    file: UploadFile,
    token: dm.AuthToken = Depends(get_current_token),
    media_service: MediaService = Depends(get_media_service),
) -> MediaDTO:
    url = await media_service.save(file.filename, file.content_type, await file.read())
    return MediaDTO(photo_url=url)


@router.get("/media/{MediaID}")
async def get_media(
    media_id: Annotated[int, Path(alias="MediaID")],
    media_service: MediaService = Depends(get_media_service),
) -> Response:
    # intentionally public: photo URLs must be usable inside <img> tags
    media = await media_service.get(media_id)
    return Response(content=media.data, media_type=media.content_type)
