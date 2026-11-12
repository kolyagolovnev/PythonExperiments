"""FastAPI dependencies.

Reminder from problems.txt: every injectable argument in a route
prototype must go through Depends().
"""

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.container import Container
from app.domains import models as dm
from app.services.auth_service import AuthService
from app.services.chat_service import ChatService
from app.services.exceptions import NotAuthenticated
from app.services.group_service import GroupService
from app.services.media_service import MediaService
from app.services.paste_service import PasteService
from app.services.sign_service import SignService
from app.services.user_service import UserService

# auto_error=False so a missing/invalid Authorization header becomes
# our own 401 instead of FastAPI's default 403.
bearer_scheme = HTTPBearer(auto_error=False)


def get_container(request: Request) -> Container:
    return request.app.state.container


def get_auth_service(container: Container = Depends(get_container)) -> AuthService:
    return container.auth_service


def get_sign_service(container: Container = Depends(get_container)) -> SignService:
    return container.sign_service


def get_user_service(container: Container = Depends(get_container)) -> UserService:
    return container.user_service


def get_group_service(container: Container = Depends(get_container)) -> GroupService:
    return container.group_service


def get_paste_service(container: Container = Depends(get_container)) -> PasteService:
    return container.paste_service


def get_chat_service(container: Container = Depends(get_container)) -> ChatService:
    return container.chat_service


def get_media_service(container: Container = Depends(get_container)) -> MediaService:
    return container.media_service


async def get_current_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> dm.AuthToken:
    if credentials is None:
        raise NotAuthenticated()
    return auth_service.decode_token(credentials.credentials)
