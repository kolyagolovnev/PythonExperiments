from app.main import app, get_sign_service
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from typing import cast, TypeVar, Type, Any, Callable
from app.repositories import SignRepository, SignCacheRepository

client = TestClient(app)

T = TypeVar("T")

def create_mock_repo(repo_cls: Type[T]) -> Callable[[], T]:
    """Создаёт pytest-фикстуру, возвращающую типизированный мок репозитория."""
    @pytest.fixture
    def _fixture() -> T:
        return cast(T, AsyncMock(spec=repo_cls))
    return _fixture

mock_sign_repo = create_mock_repo(SignRepository)