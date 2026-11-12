"""Integration fixtures: the SQLAlchemy repository layer against real databases.

Every parity test runs twice — once on SQLite (file per test, always
available) and once on PostgreSQL via testcontainers (skipped when Docker
is unavailable). The same repository code must behave identically on both.
"""

import atexit

import pytest
from app.domains import models as dm

from app.admins import AdminRegistry
from app.container import build_container
from app.settings import Settings
from tests.conftest import ADMIN_EMAIL, TEST_SECRET, USER_PASSWORD

_postgres_url: list[str] = []


def _start_postgres() -> str | None:
    """Starts one Postgres container for the whole session; None if impossible."""
    try:
        from testcontainers.postgres import PostgresContainer

        container = PostgresContainer("postgres:17-alpine").start()
        url = container.get_connection_url(driver="asyncpg")
        atexit.register(container.stop)
        return url
    except Exception:
        return None


@pytest.fixture(scope="session")
def postgres_url() -> str | None:
    if not _postgres_url:
        _postgres_url.append(_start_postgres())
    return _postgres_url[0]


@pytest.fixture(params=["sqlite", "postgres"])
async def db_container(request, tmp_path, postgres_url):
    if request.param == "sqlite":
        url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    else:
        if postgres_url is None:
            pytest.skip("Docker is not available for the Postgres testcontainer")
        url = postgres_url

    settings = Settings(secret=TEST_SECRET, password_hash_rounds=4,
                        media_max_bytes=100, database_url=url)
    container = build_container(settings, AdminRegistry({ADMIN_EMAIL}))
    await container.setup()
    yield container
    await container.shutdown()

    if request.param == "postgres":
        # row-level cleanup + sequence reset: the container (and its data) is
        # shared per session, so each test must start "factory-fresh" — same
        # semantics as the per-test SQLite file.
        from sqlalchemy import text

        from app.repositories.sqlalchemy_repos.orm import Base

        async with container.sessionmaker() as session, session.begin():
            await session.execute(text(
                "SELECT setval(pg_get_serial_sequence(t, c), 1, false) FROM ("
                "  VALUES ('accounts','id'), ('users','id'), ('groups','id'),"
                "         ('subscriptions','id'), ('pastes','id'), ('comments','id'),"
                "         ('chats','id'), ('messages','id'), ('media','id')"
                ") AS v(t, c)"
            ))
            for table in reversed(Base.metadata.sorted_tables):
                await session.execute(text(f'DELETE FROM "{table.name}"'))


@pytest.fixture
async def db_users(db_container):
    """Three signed-up users; returns a token factory (admins minted manually)."""
    for email in ("a@t.com", "b@t.com", "c@t.com"):
        await db_container.sign_service.sign_up(
            dm.SignUpData(email=email, password=USER_PASSWORD)
        )

    def token_for(user_id: int, role: dm.Role = dm.Role.USER) -> dm.AuthToken:
        return db_container.auth_service.issue_token(user_id, role)

    return token_for
