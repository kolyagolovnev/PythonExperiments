"""Tests for the startup example-data seeder."""

import json

import pytest

from app.admins import AdminRegistry
from app.container import build_container
from app.domains import models as dm
from app.seed import (
    load_seed_accounts,
    load_seed_groups,
    parse_group_description,
    seed_examples,
)
from app.settings import Settings
from tests.conftest import TEST_SECRET

ADMIN_EMAIL = "admin@seed.test"
USER_EMAILS = ("user1@seed.test", "user2@seed.test")
JPEG = b"\xff\xd8\xff\xe0seeded-avatar"
PNG = b"\x89PNG\r\n\x1a\nseeded-avatar"


def _write_examples(tmp_path) -> tuple:
    accounts_dir = tmp_path / "account_examples"
    accounts_dir.mkdir()
    profiles = [
        {
            "email": ADMIN_EMAIL,
            "password": "Admin12345!",
            "role": "admin",
            "name": "Ivan",
            "surname": "Adminov",
            "rang": 5,
        },
        {
            "username": USER_EMAILS[0],
            "password": "User12345!",
            "name": "Petr",
            "surname": "Sergeev",
        },
        {
            "email": USER_EMAILS[1],
            "password": "User12345!",
            "is_admin": False,
        },
    ]
    for number, profile in enumerate(profiles, start=1):
        (accounts_dir / f"profile{number}.json").write_text(
            json.dumps(profile), encoding="utf-8"
        )
    for number in range(1, 4):
        (accounts_dir / f"military{number}.jpeg").write_bytes(JPEG)

    groups_dir = tmp_path / "group_examples"
    groups_dir.mkdir()
    (groups_dir / "description1.txt").write_text(
        "Название группы: Ярые фанаты ОМОНа\n\n"
        "Описание: Группа для тех, кто ловит хулиганов\n",
        encoding="utf-8",
    )
    (groups_dir / "description2.txt").write_text(
        "Название: Отчаянные пилоты\n\n"
        "Описание: Для тех, кого самолеты интересуют больше девушек\n",
        encoding="utf-8",
    )
    (groups_dir / "avatar1.png").write_bytes(PNG)
    (groups_dir / "avatar2.png").write_bytes(PNG)
    return accounts_dir, groups_dir


def _settings(accounts_dir, groups_dir, **overrides) -> Settings:
    return Settings(
        secret=TEST_SECRET,
        password_hash_rounds=4,
        account_examples_dir=accounts_dir,
        group_examples_dir=groups_dir,
        **overrides,
    )


class TestGroupDescriptionParsing:

    def test_parses_both_russian_name_labels(self):
        assert parse_group_description(
            "Название группы: ОМОН\n\nОписание: Строгие ребята\n"
        ) == ("ОМОН", "Строгие ребята")
        assert parse_group_description(
            "Название: Пилоты\n\nОписание: Любят небо\n"
        ) == ("Пилоты", "Любят небо")

    def test_keeps_multiline_description(self):
        name, description = parse_group_description(
            "Name: Pilots\nDescription: First line\nSecond line\n\nThird line\n"
        )
        assert name == "Pilots"
        assert description == "First line\nSecond line\nThird line"


class TestLoadingExamples:

    def test_loads_accounts_and_accepts_username_alias(self, tmp_path):
        accounts_dir, groups_dir = _write_examples(tmp_path)
        accounts = load_seed_accounts(accounts_dir)

        assert [account.email for account in accounts] == [
            ADMIN_EMAIL,
            USER_EMAILS[0],
            USER_EMAILS[1],
        ]
        assert accounts[0].is_admin is True
        assert accounts[1].is_admin is False
        assert accounts[0].name == "Ivan"
        assert accounts[0].rang == 5
        assert [account.avatar for account in accounts] == [
            accounts_dir / "military1.jpeg",
            accounts_dir / "military2.jpeg",
            accounts_dir / "military3.jpeg",
        ]

        groups = load_seed_groups(groups_dir)
        assert [group.name for group in groups] == [
            "Ярые фанаты ОМОНа",
            "Отчаянные пилоты",
        ]
        assert groups[0].avatar == groups_dir / "avatar1.png"
        assert groups[1].avatar == groups_dir / "avatar2.png"

    def test_explicit_avatar_field_wins(self, tmp_path):
        accounts_dir = tmp_path / "account_examples"
        accounts_dir.mkdir()
        (accounts_dir / "profile1.json").write_text(
            json.dumps(
                {
                    "email": ADMIN_EMAIL,
                    "password": "Admin12345!",
                    "avatar": "custom.jpeg",
                }
            ),
            encoding="utf-8",
        )
        (accounts_dir / "custom.jpeg").write_bytes(JPEG)
        (accounts_dir / "military1.jpeg").write_bytes(JPEG)

        accounts = load_seed_accounts(accounts_dir)

        assert accounts[0].avatar == accounts_dir / "custom.jpeg"

    def test_missing_directories_are_not_an_error(self, tmp_path):
        assert load_seed_accounts(tmp_path / "missing") == []
        assert load_seed_groups(tmp_path / "missing-dir") == []


class TestSeeding:

    async def test_creates_accounts_profiles_groups_and_avatars(self, tmp_path):
        accounts_dir, groups_dir = _write_examples(tmp_path)
        container = build_container(
            _settings(accounts_dir, groups_dir), AdminRegistry({ADMIN_EMAIL})
        )

        await seed_examples(container)

        admin = await container.account_repo.find_by_email(ADMIN_EMAIL)
        assert admin is not None
        assert admin.role == dm.Role.ADMIN

        for email in USER_EMAILS:
            account = await container.account_repo.find_by_email(email)
            assert account is not None
            assert account.role == dm.Role.USER

        user = await container.user_repo.get(admin.id)
        assert (user.name, user.surname, user.rang) == ("Ivan", "Adminov", 5)
        assert user.photo_url.startswith("/media/")
        media = await container.media_service.get(
            int(user.photo_url.rsplit("/", 1)[1])
        )
        assert media.filename == "military1.jpeg"
        assert media.content_type == "image/jpeg"
        assert media.data == JPEG

        groups = await container.group_repo.search(None, limit=100, offset=0)
        assert {group.name for group in groups} == {
            "Ярые фанаты ОМОНа",
            "Отчаянные пилоты",
        }

        for item in groups:
            group = await container.group_repo.get(item.id)
            assert group.photo_url.startswith("/media/")
            media_id = int(group.photo_url.rsplit("/", 1)[1])
            media = await container.media_service.get(media_id)
            assert media.content_type == "image/png"
            assert media.data == PNG

        group = await container.group_repo.get(groups[0].id)
        assert group.description == "Группа для тех, кто ловит хулиганов"

    async def test_is_idempotent(self, tmp_path):
        accounts_dir, groups_dir = _write_examples(tmp_path)
        container = build_container(
            _settings(accounts_dir, groups_dir), AdminRegistry({ADMIN_EMAIL})
        )

        await seed_examples(container)
        admin = await container.account_repo.find_by_email(ADMIN_EMAIL)
        user_before = await container.user_repo.get(admin.id)

        await seed_examples(container)
        user_after = await container.user_repo.get(admin.id)

        assert user_after.photo_url == user_before.photo_url
        users = await container.user_repo.search(
            dm.UserSearchParams(name=None, surname=None, limit=100, offset=0)
        )
        assert len(users) == 3
        groups = await container.group_repo.search(None, limit=100, offset=0)
        assert len(groups) == 2

    async def test_backfills_a_missing_avatar_only(self, tmp_path):
        accounts_dir, groups_dir = _write_examples(tmp_path)
        container = build_container(
            _settings(accounts_dir, groups_dir), AdminRegistry({ADMIN_EMAIL})
        )

        await seed_examples(container)
        admin = await container.account_repo.find_by_email(ADMIN_EMAIL)
        user = await container.user_repo.get(admin.id)
        user.photo_url = ""
        await container.user_repo.update(user)

        await seed_examples(container)
        backfilled = await container.user_repo.get(admin.id)

        assert backfilled.photo_url.startswith("/media/")
        assert (backfilled.name, backfilled.surname) == ("Ivan", "Adminov")

    async def test_can_be_disabled(self, tmp_path):
        accounts_dir, groups_dir = _write_examples(tmp_path)
        container = build_container(
            _settings(accounts_dir, groups_dir, seed_enabled=False),
            AdminRegistry({ADMIN_EMAIL}),
        )

        await seed_examples(container)

        assert await container.account_repo.find_by_email(ADMIN_EMAIL) is None
        assert await container.group_repo.search(None, limit=100, offset=0) == []

    async def test_groups_are_skipped_without_an_admin(self, tmp_path):
        accounts_dir, groups_dir = _write_examples(tmp_path)
        container = build_container(
            _settings(accounts_dir, groups_dir), AdminRegistry(set())
        )

        await seed_examples(container)

        # The account exists but is a regular user; group creation needs admin.
        admin = await container.account_repo.find_by_email(ADMIN_EMAIL)
        assert admin is not None
        assert admin.role == dm.Role.USER
        assert await container.group_repo.search(None, limit=100, offset=0) == []

    @pytest.mark.parametrize("content", ["not json", "[]", '{"accounts": 3}'])
    async def test_bad_account_profile_is_ignored(self, tmp_path, content):
        accounts_dir = tmp_path / "account_examples"
        accounts_dir.mkdir()
        (accounts_dir / "profile1.json").write_text(content, encoding="utf-8")
        groups_dir = tmp_path / "group_examples"
        groups_dir.mkdir()

        container = build_container(
            _settings(accounts_dir, groups_dir), AdminRegistry({ADMIN_EMAIL})
        )
        await seed_examples(container)

        assert await container.account_repo.find_by_email(ADMIN_EMAIL) is None
