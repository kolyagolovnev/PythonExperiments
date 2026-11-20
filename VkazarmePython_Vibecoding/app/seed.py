"""Example data seeding for first start and repeated runs.

The seeder is deliberately small and file-driven:

- ``account_examples/`` holds one JSON profile per account (email + password +
  optional profile fields), plus the account avatars. An avatar is paired with
  a profile by the number in the file name (``profile1.json`` ->
  ``military1.jpeg``); the profile may also name it explicitly with an
  ``"avatar": "file.jpeg"`` field. An account marked as admin must also be
  listed in ``admins.json``, because that is the project's single source of
  truth for the admin role.
- ``group_examples/description*.txt`` files describe topic groups:
  "Название группы: ..." / "Название: ..." and "Описание: ...".
  An avatar is paired by the number in the file name
  (``description1.txt`` -> ``avatar1.png``; other image extensions work too).

Seeding is idempotent: accounts are created only when the email is unknown,
and groups only when a topic group with the same name does not exist. Existing
profiles are not overwritten; a missing avatar is filled in without touching
the rest of the profile. Everything is best-effort: a malformed example file
is logged and skipped instead of preventing the application from starting.
"""

import json
import logging
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from app.container import Container
from app.domains import models as dm

logger = logging.getLogger(__name__)

_NAME_RE = re.compile(
    r"^\s*(?:название(?:\s+группы)?|name)\s*:\s*(?P<value>.*)$", re.IGNORECASE
)
_DESCRIPTION_RE = re.compile(
    r"^\s*(?:описание|description)\s*:\s*(?P<value>.*)$", re.IGNORECASE
)
_NUMBER_RE = re.compile(r"(\d+)")

_IMAGE_CONTENT_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


@dataclass(frozen=True)
class SeedAccount:
    email: str
    password: str
    is_admin: bool = False
    name: str | None = None
    surname: str | None = None
    job: str | None = None
    rang: int | None = None
    status: str | None = None
    subdivision: str | None = None
    photo_url: str | None = None
    avatar: Path | None = None

    def profile_patch(self) -> dm.UserPatch:
        return dm.UserPatch(
            name=self.name,
            surname=self.surname,
            job=self.job,
            rang=self.rang,
            status=self.status,
            subdivision=self.subdivision,
            photo_url=self.photo_url,
        )


@dataclass(frozen=True)
class SeedGroup:
    name: str
    description: str = ""
    avatar: Path | None = None


def _natural_key(path: Path) -> tuple[int, str]:
    match = _NUMBER_RE.search(path.stem)
    return (int(match.group(1)) if match else 10**9, path.name.lower())


def _optional_str(entry: dict[str, Any], field: str) -> str | None:
    value = entry.get(field)
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _optional_int(entry: dict[str, Any], field: str) -> int | None:
    value = entry.get(field)
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        logger.warning("Seed account field %r is not an integer; ignoring it", field)
        return None


def _is_admin(entry: dict[str, Any]) -> bool:
    role = str(entry.get("role", "")).strip().lower()
    marker = entry.get("is_admin", entry.get("admin", False))
    return role == "admin" or marker is True


def _account_from_entry(entry: dict[str, Any], source: Path,
                        position: int) -> SeedAccount | None:
    # "username" is accepted as an alias for "email" so the file stays
    # friendly to the task wording; the application itself logs in by email.
    email = str(entry.get("email") or entry.get("username") or "").strip()
    password = entry.get("password")
    if not email or not isinstance(password, str) or not password:
        logger.warning(
            "Account profile #%d in %s has no email/username or password",
            position,
            source,
        )
        return None
    return SeedAccount(
        email=email,
        password=password,
        is_admin=_is_admin(entry),
        name=_optional_str(entry, "name"),
        surname=_optional_str(entry, "surname"),
        job=_optional_str(entry, "job"),
        rang=_optional_int(entry, "rang"),
        status=_optional_str(entry, "status"),
        subdivision=_optional_str(entry, "subdivision"),
        photo_url=_optional_str(entry, "photo_url"),
    )


def _profile_entries(raw: Any, source: Path) -> list[dict[str, Any]]:
    """Accepts a single profile object, a list, or {"accounts": [...]}."""
    if isinstance(raw, dict) and "accounts" in raw:
        raw = raw["accounts"]
    elif isinstance(raw, dict):
        raw = [raw]

    if not isinstance(raw, list):
        logger.error("Account profile %s must contain an object or a list", source)
        return []

    entries: list[dict[str, Any]] = []
    for position, entry in enumerate(raw, start=1):
        if not isinstance(entry, dict):
            logger.warning("Account profile #%d in %s is not an object", position, source)
            continue
        entries.append(entry)
    return entries


def _pick_account_avatar(directory: Path, profile: Path, used: set[Path],
                         explicit: str | None = None) -> Path | None:
    images = sorted(
        (
            path
            for path in directory.iterdir()
            if path.is_file()
            and path.suffix.lower() in _IMAGE_CONTENT_TYPES
            and path not in used
        ),
        key=_natural_key,
    )

    if explicit:
        candidate = directory / explicit
        if (
            candidate.is_file()
            and candidate.parent == directory
            and candidate.suffix.lower() in _IMAGE_CONTENT_TYPES
            and candidate not in used
        ):
            return candidate
        logger.warning("Avatar %r for %s was not found or is already used", explicit, profile)

    if not images:
        return None

    match = _NUMBER_RE.search(profile.stem)
    if match:
        expected = int(match.group(1))
        for image in images:
            image_match = _NUMBER_RE.search(image.stem)
            if image_match and int(image_match.group(1)) == expected:
                return image

    # No image with the profile's number: use the next unused image so a
    # simple directory with profiles and avatars still works.
    return images[0]


def load_seed_accounts(directory: Path) -> list[SeedAccount]:
    """Reads profile JSON files and pairs each with an avatar image."""
    if not directory.is_dir():
        logger.info(
            "No account example directory at %s; skipping account seeding",
            directory,
        )
        return []

    profile_files = sorted(
        (
            path
            for path in directory.iterdir()
            if path.is_file()
            and path.suffix.lower() == ".json"
            and not path.name.startswith(".")
        ),
        key=_natural_key,
    )
    if not profile_files:
        logger.info("No account profile JSON files in %s", directory)
        return []

    accounts: list[SeedAccount] = []
    used_avatars: set[Path] = set()
    for profile_file in profile_files:
        try:
            raw = json.loads(profile_file.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            logger.exception("Could not read account profile %s", profile_file)
            continue

        for position, entry in enumerate(_profile_entries(raw, profile_file), start=1):
            seed = _account_from_entry(entry, profile_file, position)
            if seed is None:
                continue

            avatar = _pick_account_avatar(
                directory,
                profile_file,
                used_avatars,
                explicit=_optional_str(entry, "avatar"),
            )
            if avatar is not None:
                used_avatars.add(avatar)
            else:
                logger.warning("No avatar found for account %r", seed.email)

            accounts.append(replace(seed, avatar=avatar))
    return accounts


def parse_group_description(text: str) -> tuple[str, str]:
    """Extracts (name, description) from a description*.txt file.

    The expected human-readable format is:

        Название группы: Ярые фанаты ОМОНа

        Описание: Группа для тех, кто ...

    "Название:"/"Name:" and "Описание:"/"Description:" are accepted too.
    Continuation lines after the description label are kept.
    """
    name = ""
    description_lines: list[str] = []
    in_description = False

    for line in text.splitlines():
        name_match = _NAME_RE.match(line)
        if name_match:
            if not name:
                name = name_match.group("value").strip()
            in_description = False
            continue

        description_match = _DESCRIPTION_RE.match(line)
        if description_match:
            in_description = True
            value = description_match.group("value").strip()
            if value:
                description_lines.append(value)
            continue

        if in_description:
            stripped = line.strip()
            if stripped:
                description_lines.append(stripped)

    return name, "\n".join(description_lines).strip()


def _pick_group_avatar(directory: Path, description: Path,
                       used: set[Path]) -> Path | None:
    images = sorted(
        (
            path
            for path in directory.iterdir()
            if path.is_file()
            and path.suffix.lower() in _IMAGE_CONTENT_TYPES
            and path not in used
        ),
        key=_natural_key,
    )
    if not images:
        return None

    match = _NUMBER_RE.search(description.stem)
    if match:
        expected = f"avatar{match.group(1)}"
        for image in images:
            if image.stem.lower() == expected:
                return image

    # No avatarN.<ext> for this description: use the next unused image so a
    # simple folder with description files and avatars still works.
    return images[0]


def load_seed_groups(directory: Path) -> list[SeedGroup]:
    """Reads group descriptions and pairs each with an avatar."""
    if not directory.is_dir():
        logger.info("No group example directory at %s; skipping group seeding", directory)
        return []

    description_files = sorted(
        (
            path
            for path in directory.iterdir()
            if path.is_file()
            and path.suffix.lower() == ".txt"
            and not path.name.startswith(".")
            and path.stem.lower() != "readme"
        ),
        key=_natural_key,
    )
    if not description_files:
        logger.info("No group description files in %s", directory)
        return []

    groups: list[SeedGroup] = []
    used_avatars: set[Path] = set()
    for description_file in description_files:
        try:
            text = description_file.read_text(encoding="utf-8-sig")
        except OSError:
            logger.exception("Could not read group description %s", description_file)
            continue

        name, description = parse_group_description(text)
        if not name:
            match = _NUMBER_RE.search(description_file.stem)
            name = f"Group {match.group(1)}" if match else description_file.stem
            logger.warning(
                "No group name in %s; falling back to %r",
                description_file,
                name,
            )

        avatar = _pick_group_avatar(directory, description_file, used_avatars)
        if avatar is not None:
            used_avatars.add(avatar)
        else:
            logger.warning("No avatar found for group %r", name)

        groups.append(SeedGroup(name=name, description=description, avatar=avatar))

    return groups


async def _upload_avatar(container: Container, avatar: Path | None,
                         label: str) -> str:
    if avatar is None:
        return ""
    content_type = _IMAGE_CONTENT_TYPES.get(avatar.suffix.lower())
    if content_type is None:
        logger.warning("Unsupported avatar type for %s: %s", label, avatar)
        return ""
    try:
        return await container.media_service.save(
            avatar.name,
            content_type,
            avatar.read_bytes(),
        )
    except Exception:
        logger.exception("Could not upload the avatar for %s", label)
        return ""


async def _apply_profile(container: Container, account: dm.Account,
                         seed: SeedAccount, photo_url: str | None = None) -> None:
    patch = seed.profile_patch()
    if photo_url:
        patch.photo_url = photo_url
    if not any(value is not None for value in vars(patch).values()):
        return
    token = container.auth_service.issue_token(account.id, account.role)
    try:
        await container.user_service.patch_user(token, account.id, patch)
    except Exception:
        logger.exception("Could not apply the example profile for %s", seed.email)


async def _backfill_avatar(container: Container, account: dm.Account,
                           seed: SeedAccount) -> None:
    """Adds a missing avatar to an existing example account, nothing else."""
    if seed.avatar is None:
        return
    try:
        user = await container.user_repo.get(account.id)
    except Exception:
        logger.exception("Could not inspect the profile for %s", seed.email)
        return
    if user.photo_url:
        return

    photo_url = await _upload_avatar(container, seed.avatar, f"account {seed.email}")
    if not photo_url:
        return

    token = container.auth_service.issue_token(account.id, account.role)
    try:
        await container.user_service.patch_user(
            token, account.id, dm.UserPatch(photo_url=photo_url)
        )
    except Exception:
        logger.exception("Could not add the example avatar for %s", seed.email)
    else:
        logger.info("Added the example avatar for %s", seed.email)


async def _seed_accounts(container: Container, accounts: list[SeedAccount]) -> dm.AuthToken | None:
    admin_token: dm.AuthToken | None = None

    for seed in accounts:
        account = await container.account_repo.find_by_email(seed.email)
        if account is None:
            try:
                await container.sign_service.sign_up(
                    dm.SignUpData(email=seed.email, password=seed.password)
                )
            except Exception:
                logger.exception("Could not create example account %s", seed.email)
                continue

            account = await container.account_repo.find_by_email(seed.email)
            if account is None:
                logger.error("Example account %s disappeared after signup", seed.email)
                continue

            photo_url = await _upload_avatar(
                container, seed.avatar, f"account {seed.email}"
            )
            logger.info("Created example account %s", seed.email)
            await _apply_profile(container, account, seed, photo_url or None)
        else:
            logger.info("Example account %s already exists; leaving it unchanged", seed.email)
            await _backfill_avatar(container, account, seed)

        if seed.is_admin and account.role != dm.Role.ADMIN:
            logger.error(
                "Example account %s is marked as admin, but its role is %r. "
                "Add %s to admins.json before the first startup.",
                seed.email,
                account.role.value,
                seed.email,
            )

        if account.role == dm.Role.ADMIN and admin_token is None:
            admin_token = container.auth_service.issue_token(account.id, account.role)

    return admin_token


async def _find_topic_group(container: Container, name: str) -> dm.Group | None:
    found = await container.group_repo.search(name, limit=100, offset=0)
    expected = name.casefold()
    for item in found:
        if item.name.casefold() == expected:
            return await container.group_repo.get(item.id)
    return None


async def _seed_groups(container: Container, groups: list[SeedGroup],
                       admin_token: dm.AuthToken | None) -> None:
    if not groups:
        return
    if admin_token is None:
        logger.warning(
            "Cannot create example groups: no account profile from "
            "account_examples/ has the admin role"
        )
        return

    for seed in groups:
        if await _find_topic_group(container, seed.name) is not None:
            logger.info("Example group %r already exists; leaving it unchanged", seed.name)
            continue

        photo_url = await _upload_avatar(container, seed.avatar, f"group {seed.name!r}")

        try:
            await container.group_service.create_group(
                admin_token,
                dm.GroupPost(
                    name=seed.name,
                    description=seed.description,
                    photo_url=photo_url,
                ),
            )
        except Exception:
            logger.exception("Could not create example group %r", seed.name)
        else:
            logger.info("Created example group %r", seed.name)


async def seed_examples(container: Container, accounts_dir: Path | None = None,
                        groups_dir: Path | None = None) -> None:
    """Creates example accounts and groups from the configured directories.

    Safe to call on every startup: existing entities are left untouched apart
    from a missing example avatar, which is filled in.
    """
    settings = container.settings
    if not settings.seed_enabled:
        logger.info("Example data seeding is disabled (SEED_ENABLED=false)")
        return

    accounts = load_seed_accounts(accounts_dir or settings.account_examples_dir)
    admin_token = await _seed_accounts(container, accounts)

    groups = load_seed_groups(groups_dir or settings.group_examples_dir)
    await _seed_groups(container, groups, admin_token)
