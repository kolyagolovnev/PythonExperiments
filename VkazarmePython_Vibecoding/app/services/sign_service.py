"""Registration and sign-in.

On signup three things are created atomically (in-memory for now):
the account (email + bcrypt hash + role from the admins file),
the user's personal group, and the user profile linked to that group.
"""

import re

import bcrypt

from app.admins import AdminRegistry
from app.domains import models as dm
from app.repositories.interfaces import AccountRepository, GroupRepository, UserRepository
from app.services.auth_service import AuthService
from app.services.exceptions import EmailIsBusy, IncorrectEmailOrPassword, InvalidEmail
from app.settings import Settings

# Same pragmatic pattern the project used before; EmailStr already
# validates at the boundary, this guards direct service use.
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


class SignService:
    def __init__(
        self,
        account_repo: AccountRepository,
        user_repo: UserRepository,
        group_repo: GroupRepository,
        auth_service: AuthService,
        admins: AdminRegistry,
        settings: Settings,
    ):
        self._account_repo = account_repo
        self._user_repo = user_repo
        self._group_repo = group_repo
        self._auth_service = auth_service
        self._admins = admins
        self._settings = settings

    async def sign_up(self, data: dm.SignUpData) -> None:
        if not _EMAIL_RE.match(data.email):
            raise InvalidEmail()
        if await self._account_repo.find_by_email(data.email) is not None:
            raise EmailIsBusy()

        hashed_password = bcrypt.hashpw(
            data.password.encode(),
            bcrypt.gensalt(rounds=self._settings.password_hash_rounds),
        )
        role = dm.Role.ADMIN if self._admins.is_admin(data.email) else dm.Role.USER
        account = await self._account_repo.add(
            dm.Account(id=0, email=data.email, hashed_password=hashed_password, role=role)
        )
        personal_group = await self._group_repo.add(
            dm.Group(id=0, name=data.email, owner_id=account.id)
        )
        await self._user_repo.add(
            dm.User(id=account.id, personal_group_id=personal_group.id)
        )

    async def sign_in(self, request: dm.SignInRequest) -> dm.AuthToken:
        account = await self._account_repo.find_by_email(request.email)
        if account is None or not bcrypt.checkpw(
            request.password.encode(), account.hashed_password
        ):
            raise IncorrectEmailOrPassword()
        return self._auth_service.issue_token(account.id, account.role)
