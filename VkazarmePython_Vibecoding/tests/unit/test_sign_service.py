"""SignService unit tests: registration, personal group creation, sign-in, JWT."""

import bcrypt
import jwt as pyjwt
import pytest

from app.admins import AdminRegistry
from app.container import build_container
from app.domains import models as dm
from app.services import exceptions as sex
from app.settings import Settings
from tests.conftest import ADMIN_EMAIL, TEST_SECRET, USER_PASSWORD


def make_service(admins: set[str] | None = None):
    container = build_container(Settings(secret=TEST_SECRET), AdminRegistry(admins or set()))
    return container


class TestSignUp:

    async def test_signup_creates_account_user_and_personal_group(self):
        container = make_service()
        await container.sign_service.sign_up(dm.SignUpData(email="a@t.com", password=USER_PASSWORD))

        account = await container.account_repo.find_by_email("a@t.com")
        assert account is not None
        user = await container.user_repo.get(account.id)
        group = await container.group_repo.get(user.personal_group_id)
        assert group.owner_id == account.id
        assert group.is_personal

    async def test_signup_hashes_password_with_salt(self):
        container = make_service()
        await container.sign_service.sign_up(dm.SignUpData(email="a@t.com", password=USER_PASSWORD))

        account = await container.account_repo.find_by_email("a@t.com")
        assert account.hashed_password != USER_PASSWORD.encode()
        assert bcrypt.checkpw(USER_PASSWORD.encode(), account.hashed_password)

    async def test_signup_rejects_duplicate_email_case_insensitive(self):
        container = make_service()
        await container.sign_service.sign_up(dm.SignUpData(email="a@t.com", password=USER_PASSWORD))

        with pytest.raises(sex.EmailIsBusy):
            await container.sign_service.sign_up(
                dm.SignUpData(email="A@T.COM", password=USER_PASSWORD)
            )

    async def test_signup_rejects_malformed_email(self):
        container = make_service()
        with pytest.raises(sex.InvalidEmail):
            await container.sign_service.sign_up(
                dm.SignUpData(email="not-an-email", password=USER_PASSWORD)
            )

    async def test_admin_email_gets_admin_role(self):
        container = make_service(admins={ADMIN_EMAIL})
        await container.sign_service.sign_up(
            dm.SignUpData(email=ADMIN_EMAIL, password=USER_PASSWORD)
        )
        account = await container.account_repo.find_by_email(ADMIN_EMAIL)
        assert account.role == dm.Role.ADMIN


class TestSignIn:

    async def test_signin_returns_token_with_correct_claims(self):
        container = make_service()
        await container.sign_service.sign_up(dm.SignUpData(email="a@t.com", password=USER_PASSWORD))

        token = await container.sign_service.sign_in(
            dm.SignInRequest(email="a@t.com", password=USER_PASSWORD)
        )
        assert token.sub == 1
        assert token.exp > 0
        assert token.role == dm.Role.USER
        # raw token decodes back to the same claims
        payload = pyjwt.decode(token.raw, TEST_SECRET, algorithms=["HS256"])
        assert payload["sub"] == "1"
        assert payload["role"] == "user"

    async def test_signin_wrong_password_raises_403_error(self):
        container = make_service()
        await container.sign_service.sign_up(dm.SignUpData(email="a@t.com", password=USER_PASSWORD))

        with pytest.raises(sex.IncorrectEmailOrPassword):
            await container.sign_service.sign_in(
                dm.SignInRequest(email="a@t.com", password="WrongPassword")
            )

    async def test_signin_unknown_email_raises_403_error(self):
        container = make_service()
        with pytest.raises(sex.IncorrectEmailOrPassword):
            await container.sign_service.sign_in(
                dm.SignInRequest(email="ghost@t.com", password=USER_PASSWORD)
            )

    async def test_signin_after_signup_as_admin_yields_admin_role(self):
        container = make_service(admins={ADMIN_EMAIL})
        await container.sign_service.sign_up(
            dm.SignUpData(email=ADMIN_EMAIL, password=USER_PASSWORD)
        )
        token = await container.sign_service.sign_in(
            dm.SignInRequest(email=ADMIN_EMAIL, password=USER_PASSWORD)
        )
        assert token.role == dm.Role.ADMIN
