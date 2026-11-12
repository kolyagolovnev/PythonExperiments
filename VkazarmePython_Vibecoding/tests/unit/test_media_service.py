"""MediaService unit tests: validation rules and storage roundtrip."""

import pytest

from app.container import build_container
from app.services import exceptions as sex
from app.settings import Settings
from tests.conftest import TEST_SECRET

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"fake-png-body"


@pytest.fixture
def container():
    return build_container(Settings(secret=TEST_SECRET))


@pytest.fixture
def tiny_container():
    return build_container(
        Settings(secret=TEST_SECRET, media_max_bytes=100)
    )


class TestSave:

    async def test_valid_image_returns_relative_url(self, container):
        url = await container.media_service.save("avatar.png", "image/png", PNG_BYTES)
        assert url.startswith("/media/")
        assert url.split("/")[-1].isdigit()

    @pytest.mark.parametrize("content_type", [
        "image/jpeg", "image/gif", "image/webp",
    ])
    async def test_all_allowed_image_types(self, container, content_type):
        url = await container.media_service.save("photo", content_type, PNG_BYTES)
        assert url.startswith("/media/")

    async def test_unsupported_type_is_rejected(self, container):
        with pytest.raises(sex.UnsupportedMediaType):
            await container.media_service.save("doc.pdf", "application/pdf", b"%PDF-1.4")
        with pytest.raises(sex.UnsupportedMediaType):
            await container.media_service.save("notes.txt", "text/plain", b"hello")

    async def test_empty_file_is_rejected(self, container):
        with pytest.raises(sex.EmptyMediaFile):
            await container.media_service.save("avatar.png", "image/png", b"")

    async def test_oversized_file_is_rejected(self, tiny_container):
        with pytest.raises(sex.MediaTooLarge):
            await tiny_container.media_service.save(
                "big.png", "image/png", b"x" * 101
            )

    async def test_file_exactly_at_limit_is_accepted(self, tiny_container):
        url = await tiny_container.media_service.save(
            "ok.png", "image/png", b"x" * 100
        )
        assert url.startswith("/media/")


class TestGet:

    async def test_roundtrip_preserves_bytes_and_type(self, container):
        url = await container.media_service.save("avatar.png", "image/png", PNG_BYTES)
        media = await container.media_service.get(int(url.rsplit("/", 1)[-1]))
        assert media.data == PNG_BYTES
        assert media.content_type == "image/png"
        assert media.filename == "avatar.png"

    async def test_unknown_media_is_404(self, container):
        with pytest.raises(Exception):  # repository MediaNotFound
            await container.media_service.get(999)
