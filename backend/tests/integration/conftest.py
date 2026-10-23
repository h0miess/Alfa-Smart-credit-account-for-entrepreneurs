from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path
from uuid import UUID

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
from core.dependencies.auth import get_auth_service
from domain.entities.user import UserRole
from infra.notify.listener import PostgresEventListener
from infra.postgres.database import create_sessionmaker
from infra.postgres.mappings import start_mappers
from infra.postgres.models import metadata
from seed.loader import load_seed
from tests.fakes import (
    FakeAuthService,
    FakeDocumentStorage,
    FakeScoringGateway,
    FakeTaskQueue,
)
from tests.integration.pipeline import disburse, http_client, process  # noqa: F401

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
def task_queue() -> FakeTaskQueue:
    return FakeTaskQueue()


@pytest.fixture
def storage() -> FakeDocumentStorage:
    return FakeDocumentStorage()


@pytest.fixture
async def app(
    sessionmaker: async_sessionmaker[AsyncSession],
    task_queue: FakeTaskQueue,
    storage: FakeDocumentStorage,
    postgres_url: str,
) -> AsyncIterator[FastAPI]:
    app = create_app()
    async with app.router.lifespan_context(app):
        app.state.sessionmaker = sessionmaker
        app.state.scoring = FakeScoringGateway()
        app.state.task_queue = task_queue
        app.state.storage = storage
        app.state.events = PostgresEventListener(postgres_url.replace("+asyncpg", ""))
        yield app
        await app.state.events.stop()


@pytest.fixture
def login(app: FastAPI) -> Callable[[UUID, UserRole], None]:
    def login_as(user_id: UUID, role: UserRole = UserRole.CLIENT) -> None:
        app.dependency_overrides[get_auth_service] = lambda: FakeAuthService(
            user_id, role
        )

    return login_as


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def mock_user_id() -> str:
    assert settings.app.MOCK_USER_UUID
    return str(settings.app.MOCK_USER_UUID)
