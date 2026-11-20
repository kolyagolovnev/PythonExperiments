"""Application factory and HTTP error mapping."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.admins import AdminRegistry
from app.api import account_router, chats_router, groups_router, media_router, users_router
from app.container import Container, build_container
from app.middleware import FrontendMiddleware
from app.repositories import exceptions as rex
from app.seed import seed_examples
from app.services import exceptions as sex
from app.settings import Settings

logger = logging.getLogger(__name__)

_DESCRIPTION = """The goal of the work is to develop a social network for former fellow servicemen.

The provided capability is to enable simplified search and communication
for those who served in the same unit, would like to learn more about their unit, etc.

# Brief list of functional requirements

- Creating and editing your profile
- Posting entries on your profile
- Searching, adding, and removing friends
- Communicating with friends in chat
- Searching, subscribing to, and unsubscribing from groups
- Ability to leave comments on group and user posts
"""

# service/repository exception -> (HTTP status, default detail)
_ERROR_MAP: dict[type[Exception], tuple[int, str]] = {
    # sign
    sex.InvalidEmail: (400, "Invalid email format"),
    sex.EmailIsBusy: (400, "Email is already registered"),
    sex.IncorrectEmailOrPassword: (403, "Invalid login or password"),
    # token
    sex.NotAuthenticated: (401, "Not authenticated"),
    sex.InvalidToken: (401, "Invalid token"),
    sex.TokenExpired: (401, "Token expired"),
    # users / friends / subscriptions
    sex.PermissionDenied: (403, "User does not have access rights"),
    sex.SelfFriendship: (400, "Cannot add yourself as a friend"),
    sex.AlreadySubscribed: (400, "Already subscribed to this group"),
    sex.PasteNotFound: (404, "Such a post does not exist"),
    # chats
    sex.ChatNotFound: (404, "Such a chat does not exist"),
    sex.ChatMemberNotFound: (404, "Such a chat user not found"),
    sex.AlreadyMember: (400, "User is already a chat member"),
    sex.PersonalChatFixed: (403, "Members of a personal chat cannot be changed"),
    sex.InvalidChatMembers: (400, "A personal chat requires exactly one other user"),
    sex.CannotRemoveOwner: (403, "The chat owner cannot be removed"),
    # media
    sex.MediaNotFound: (404, "Such a media file does not exist"),
    sex.UnsupportedMediaType: (400, "Unsupported media type"),
    sex.MediaTooLarge: (400, "File is too large"),
    sex.EmptyMediaFile: (400, "File is empty"),
    # repository errors that reach the API unchanged
    rex.EmailAlreadyExists: (400, "Email is already registered"),
    rex.AccountNotFound: (404, "Such an account does not exist"),
    rex.UserNotFound: (404, "Such a user does not exist"),
    rex.GroupNotFound: (404, "Such a group does not exist"),
    rex.PasteNotFound: (404, "Such a post does not exist"),
    rex.ChatNotFound: (404, "Such a chat does not exist"),
    rex.ChatMemberNotFound: (404, "Such a chat user not found"),
    rex.AlreadyMember: (400, "User is already a chat member"),
    rex.MediaNotFound: (404, "Such a media file does not exist"),
    rex.AlreadyFriends: (400, "Users are already friends"),
    rex.FriendshipNotFound: (404, "Such a friend does not exist"),
    rex.AlreadySubscribed: (400, "Already subscribed to this group"),
    rex.SubscriptionNotFound: (404, "Such a subscription does not exist"),
}


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # The spec reports malformed requests as 400, not FastAPI's default 422.
        return JSONResponse(status_code=400, content={"detail": jsonable_encoder(exc.errors())})

    for exc_class, (status_code, default_detail) in _ERROR_MAP.items():
        def make_handler(code: int, detail: str):
            async def handler(request: Request, exc) -> JSONResponse:
                # exceptions carry no args -> fall back to the mapped default detail
                return JSONResponse(status_code=code, content={"detail": str(exc) or detail})
            return handler
        app.add_exception_handler(exc_class, make_handler(status_code, default_detail))


def create_app(settings: Settings | None = None,
               container: Container | None = None) -> FastAPI:
    container = container or build_container(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        # database mode: create the schema (idempotent); in-memory: no-op
        await container.setup()
        # Example accounts/groups are best-effort: bad example files must not
        # prevent the service from starting.
        try:
            await seed_examples(container)
        except Exception:
            logger.exception("Example data seeding failed; starting without it")
        yield
        await container.shutdown()

    app = FastAPI(
        title="Social Network for Fellow Servicemen",
        version="0.3",
        description=_DESCRIPTION,
        lifespan=lifespan,
    )
    app.state.container = container
    # Cross-cutting concerns live in middleware, not in the route handlers:
    # the client is served at "/" and the API is usable from any origin.
    app.add_middleware(FrontendMiddleware)
    _register_exception_handlers(app)
    app.include_router(account_router.router)
    app.include_router(users_router.router)
    app.include_router(groups_router.router)
    app.include_router(chats_router.router)
    app.include_router(media_router.router)
    return app


app = create_app()
