from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from sqlalchemy import Connection, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.community.postgres import PostgresContainer

from app import create_app
from core.configs import settings
from infra.postgres.database import create_sessionmaker
from infra.postgres.mappings import start_mappers
from infra.postgres.models import metadata
from seed.loader import load_seed

BACKEND_DIR = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.integration


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    with PostgresContainer("postgres:18.6-bookworm", driver="asyncpg") as postgres:
        yield postgres.get_connection_url()


def _upgrade(connection: Connection) -> None:
    config = Config(BACKEND_DIR / "alembic.ini")
    config.attributes["connection"] = connection
    config.attributes["configure_logger"] = False
    command.upgrade(config, "head")


@pytest.fixture(scope="session")
async def engine(postgres_url: str) -> AsyncIterator[AsyncEngine]:
    start_mappers()
    engine = create_async_engine(postgres_url)
    async with engine.begin() as connection:
        await connection.run_sync(_upgrade)
    yield engine
    await engine.dispose()


@pytest.fixture
async def sessionmaker(
    engine: AsyncEngine,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    tables = ", ".join(table.name for table in metadata.sorted_tables)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {tables} CASCADE"))

    sessionmaker = create_sessionmaker(engine)
    async with sessionmaker() as session:
        await load_seed(session, BACKEND_DIR.parent / "seed" / "companies.json")
    yield sessionmaker


@pytest.fixture
async def app(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[FastAPI]:
    app = create_app()
    async with app.router.lifespan_context(app):
        app.state.sessionmaker = sessionmaker
        yield app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def mock_user_id() -> str:
    assert settings.app.MOCK_USER_UUID
    return str(settings.app.MOCK_USER_UUID)
