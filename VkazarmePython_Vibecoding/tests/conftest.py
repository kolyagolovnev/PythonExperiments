"""Shared fixtures.

Every test gets a fresh Container (fresh in-memory state) and its own
app instance, so tests cannot leak data into each other.
E2E tests talk to the app through an httpx AsyncClient over ASGI.
"""

import httpx
import pytest
from fastapi import FastAPI

from app.admins import AdminRegistry
from app.container import Container, build_container
from app.main import create_app
from app.settings import Settings

ADMIN_EMAIL = "admin@t.com"
USER_PASSWORD = "Password123"

TEST_SECRET = "test-secret-0123456789abcdef0123456789abcdef"


@pytest.fixture
def settings() -> Settings:
    return Settings(secret=TEST_SECRET, access_token_ttl_seconds=3600,
                    password_hash_rounds=4)


@pytest.fixture
def admins() -> AdminRegistry:
    return AdminRegistry({ADMIN_EMAIL})


@pytest.fixture
def container(settings: Settings, admins: AdminRegistry) -> Container:
    return build_container(settings, admins)


@pytest.fixture
def app(container: Container) -> FastAPI:
    return create_app(container.settings, container)


@pytest.fixture
async def client(app: FastAPI):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


async def sign_up_and_sign_in(client: httpx.AsyncClient, email: str,
                              password: str = USER_PASSWORD) -> str:
    """Registers the user (idempotently) and returns a bearer token."""
    await client.post("/account/signup", json={"email": email, "password": password})
    response = await client.post("/account/signin",
                                 json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def merge_patch_headers(token: str) -> dict[str, str]:
    return {**bearer(token), "Content-Type": "application/merge-patch+json"}
