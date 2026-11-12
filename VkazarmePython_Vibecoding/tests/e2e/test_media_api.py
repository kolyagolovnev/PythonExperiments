"""End-to-end tests for /media: upload, fetch, attach to profile.

A module-local `settings` fixture lowers the size limit so the
oversized-upload test does not need a 5 MB payload.
"""

import pytest
from httpx import AsyncClient

from app.settings import Settings
from tests.conftest import TEST_SECRET, sign_up_and_sign_in


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"fake-png-body"


@pytest.fixture
def settings() -> Settings:
    return Settings(secret=TEST_SECRET, access_token_ttl_seconds=3600,
                    password_hash_rounds=4, media_max_bytes=100)


@pytest.fixture
async def token(client: AsyncClient) -> str:
    return await sign_up_and_sign_in(client, "a@t.com")


class TestUpload:

    async def test_requires_token(self, client: AsyncClient):
        response = await client.post(
            "/media", files={"file": ("a.png", PNG_BYTES, "image/png")})
        assert response.status_code == 401

    async def test_upload_returns_photo_url(self, client: AsyncClient, token):
        response = await client.post(
            "/media", files={"file": ("avatar.png", PNG_BYTES, "image/png")},
            headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        body = response.json()
        assert body["photo_url"].startswith("/media/")
        assert body["photo_url"].split("/")[-1].isdigit()

    async def test_unsupported_type_is_400(self, client: AsyncClient, token):
        response = await client.post(
            "/media", files={"file": ("a.txt", b"hello", "text/plain")},
            headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 400

    async def test_empty_file_is_400(self, client: AsyncClient, token):
        response = await client.post(
            "/media", files={"file": ("a.png", b"", "image/png")},
            headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 400

    async def test_oversized_file_is_400(self, client: AsyncClient, token):
        response = await client.post(
            "/media", files={"file": ("big.png", b"x" * 101, "image/png")},
            headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 400

    async def test_missing_file_field_is_400(self, client: AsyncClient, token):
        response = await client.post("/media", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 400


class TestFetch:

    async def test_uploaded_file_can_be_fetched_back(self, client: AsyncClient, token):
        upload = await client.post(
            "/media", files={"file": ("avatar.png", PNG_BYTES, "image/png")},
            headers={"Authorization": f"Bearer {token}"})
        url = upload.json()["photo_url"]

        # no authentication: photo URLs must work inside <img> tags
        response = await client.get(url)
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.content == PNG_BYTES

    async def test_unknown_media_is_404(self, client: AsyncClient):
        response = await client.get("/media/999")
        assert response.status_code == 404


class TestAttachToProfile:

    async def test_uploaded_url_can_become_the_avatar(self, client: AsyncClient, token):
        upload = await client.post(
            "/media", files={"file": ("avatar.png", PNG_BYTES, "image/png")},
            headers={"Authorization": f"Bearer {token}"})
        url = upload.json()["photo_url"]

        response = await client.patch("/users/1", json={"photo_url": url},
                                      headers={"Authorization": f"Bearer {token}",
                                               "Content-Type": "application/merge-patch+json"})
        assert response.status_code == 200
        profile = (await client.get("/users/1",
                                    headers={"Authorization": f"Bearer {token}"})).json()
        assert profile["photo_url"] == url
