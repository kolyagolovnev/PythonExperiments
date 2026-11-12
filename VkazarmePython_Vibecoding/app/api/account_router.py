"""/account endpoints."""

from fastapi import APIRouter, Depends, status

from app.api.deps import get_sign_service
from app.dto.account_dto import SignInRequestDTO, SignUpRequestDTO
from app.services.sign_service import SignService

router = APIRouter(tags=["account"])


@router.post("/account/signup", status_code=status.HTTP_200_OK)
async def signup(
    body: SignUpRequestDTO,
    sign_service: SignService = Depends(get_sign_service),
) -> None:
    await sign_service.sign_up(body.to_entity())


@router.post("/account/signin", response_model=str)
async def signin(
    body: SignInRequestDTO,
    sign_service: SignService = Depends(get_sign_service),
) -> str:
    token = await sign_service.sign_in(body.to_entity())
    return token.raw
