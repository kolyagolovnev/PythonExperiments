import pytest
from unittest.mock import AsyncMock, MagicMock
from dataclasses import dataclass

from app.services import SignService
from app.domains.models import SignUpData, SignRequest, AuthToken, AccountData
from app.settings import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(PASSWORD_HASH_SALT="test_salt_123")


@pytest.fixture
def repo() -> MagicMock:
    mock = MagicMock()
    # Все асинхронные методы должны быть AsyncMock
    mock.checkUserEmailExistence = AsyncMock(return_value=False)
    mock.insertAccount = AsyncMock()
    mock.findAccount = AsyncMock()
    return mock


@pytest.fixture
def service(repo, settings) -> SignService:
    return SignService(repo=repo, settings=settings)


@pytest.fixture
def valid_signup_data() -> SignUpData:
    return SignUpData(email="user@example.com", password="StrongPass123!")


@pytest.fixture
def valid_sign_request() -> SignRequest:
    return SignRequest(email="user@example.com", password="StrongPass123!")


@pytest.fixture
def expected_token() -> AuthToken:
    return AuthToken(sub="1234231", exp=3600)
