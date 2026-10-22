from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from core.configs import settings
from infra.postgres.database import create_engine, create_sessionmaker

VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # один engine (и пул соединений) на всё приложение, закрывается при остановке
    engine = create_engine(settings.postgres, settings.sql_engine)
    app.state.sessionmaker = create_sessionmaker(engine)
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Умный кредитный кабинет предпринимателя",
        version=VERSION,
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    return app
