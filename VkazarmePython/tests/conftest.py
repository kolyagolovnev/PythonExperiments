import os
import uuid
import pytest
import httpx
from typing import AsyncGenerator

# Базовый URL API (можно переопределить через переменную окружения)
# TODO: Нужно для BASE_URL определить, что надо
BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8888/api/v1")

# Тестовые учётные данные
TEST_EMAIL_DOMAIN = "e2e.local"


def _unique_email(prefix: str = "user") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}@{TEST_EMAIL_DOMAIN}"


@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE_URL


@pytest.fixture
async def client(base_url: str) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Асинхронный HTTP-клиент, живущий в течение одного теста."""
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as ac:
        yield ac


@pytest.fixture
def unique_email() -> str:
    return _unique_email()


@pytest.fixture
def signup_payload(unique_email: str) -> dict:
    """Валидный payload для регистрации.

    ВНИМАНИЕ: подставьте поля, которые реально ожидает SignUpDataDTO
    (см. dto.py). Ниже — наиболее вероятный набор.
    """
    return {
        "email": unique_email,
        "password": "StrongP@ssw0rd!",
        "name": "Иван",
        "surname": "Тестов",
        "patronymic": "Иванович",
        "birthDate": "1995-05-05",
    }


@pytest.fixture
async def registered_user(
    client: httpx.AsyncClient,
    signup_payload: dict,
) -> dict:
    """
    Регистрирует пользователя и возвращает его payload.

    Используется как зависимость в тестах signin.
    """
    resp = await client.post("/account/signup", json=signup_payload)
    # 200/201 или 409 (если e-mail уже занят) — оба варианта допустимы
    assert resp.status_code in (200, 201, 409), resp.text
    return signup_payload