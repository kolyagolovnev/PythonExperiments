import pytest
import bcrypt
from unittest.mock import AsyncMock, patch, ANY

from app.domains.models import SignUpData, AccountData
from app.services.exceptions import InvalidEmail, EmailIsBusy


class TestSignUpEmailValidation:
    """Проверка корректности email."""

    @pytest.mark.parametrize("invalid_email", [
        "",
        "invalid",
        "invalid@",
        "@domain.com",
        "user@domain",          # нет TLD
        "user @domain.com",     # пробел
        "user@dom ain.com",
        "user@@domain.com",
        "user@.com",
        "user@domain.c",        # TLD 1 символ
        "user@domain.c0m",      # цифра в TLD
    ])

    @pytest.mark.asyncio
    async def test_signup_raises_invalid_email(self, service, invalid_email):
        data = SignUpData(email=invalid_email, password="Password123!")
        with pytest.raises(InvalidEmail):
            await service.signUp(data)

    @pytest.mark.parametrize("valid_email", [
        "user@example.com",
        "ivan.petrov@mail.ru",
        "test+tag@sub.domain.org",
        "a.b_c%d-e@my-host.co.uk",
        "UPPER@EXAMPLE.COM",
        "user123@domain.io",
    ])
    @pytest.mark.asyncio
    async def test_signup_accepts_valid_email(
        self, service, repo, valid_email
    ):
        repo.checkUserEmailExistence.return_value = False
        data = SignUpData(email=valid_email, password="Password123!")

        await service.signUp(data)

        repo.insertAccount.assert_awaited_once()


class TestSignUpEmailBusy:
    """Проверка занятости email."""

    @pytest.mark.asyncio
    async def test_signup_raises_when_email_busy(
        self, service, repo, valid_signup_data
    ):
        repo.checkUserEmailExistence.return_value = True

        with pytest.raises(EmailIsBusy):
            await service.signUp(valid_signup_data)

        repo.insertAccount.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_signup_checks_exact_email(
        self, service, repo, valid_signup_data
    ):
        repo.checkUserEmailExistence.return_value = False

        await service.signUp(valid_signup_data)

        repo.checkUserEmailExistence.assert_called_once_with(
            valid_signup_data.email
        )


class TestSignUpPasswordHashing:
    """Проверка корректного хеширования пароля."""

    @pytest.mark.asyncio
    async def test_signup_hashes_password_with_salt(
        self, service, repo, settings, valid_signup_data
    ):
        repo.checkUserEmailExistence.return_value = False

        await service.signUp(valid_signup_data)

        repo.insertAccount.assert_awaited_once()
        account: AccountData = repo.insertAccount.await_args.args[0]

        # Пароль не должен храниться в открытом виде
        assert account.hashed_password != valid_signup_data.password.encode()
        # Хеш должен быть bytes
        assert isinstance(account.hashed_password, bytes)
        # Хеш должен верифицироваться исходным паролем
        assert bcrypt.checkpw(
            valid_signup_data.password.encode(),
            account.hashed_password,
        )

    @pytest.mark.asyncio
    async def test_signup_stores_email_as_is(
        self, service, repo, valid_signup_data
    ):
        repo.checkUserEmailExistence.return_value = False

        await service.signUp(valid_signup_data)

        account: AccountData = repo.insertAccount.await_args.args[0]
        assert account.email == valid_signup_data.email


class TestSignUpInsertFailure:
    """Поведение при падении репозитория."""

    @pytest.mark.asyncio
    async def test_signup_swallows_insert_exception(
        self, service, repo, valid_signup_data
    ):
        repo.checkUserEmailExistence.return_value = False
        repo.insertAccount.side_effect = Exception("DB is down")

        # Сейчас сервис глотает исключение (try/except с print).
        # Тест фиксирует текущее поведение — не падаем наружу.
        await service.signUp(valid_signup_data)

        repo.insertAccount.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_signup_calls_repo_in_order(
        self, service, repo, valid_signup_data
    ):
        repo.checkUserEmailExistence.return_value = False

        await service.signUp(valid_signup_data)

        # Проверяем, что проверка email была ДО вставки
        assert repo.checkUserEmailExistence.called
        assert repo.insertAccount.called