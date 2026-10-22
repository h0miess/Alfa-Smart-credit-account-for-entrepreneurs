from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from core.configs import settings
from infra.http.scoring import HttpScoringGateway
from infra.postgres.database import create_engine, create_sessionmaker
from infra.postgres.mappings import start_mappers
from infra.tasks.broker import broker
from infra.tasks.queue import TaskiqTaskQueue
from presentation.api.auth.token import PyJWKClientCache
from presentation.api.exceptions.handlers import setup_handlers
from presentation.api.health import health_router
from presentation.api.v1.routers import api_v1_router

VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # один engine (и пул соединений) на всё приложение, закрывается при остановке
    engine = create_engine(settings.postgres, settings.sql_engine)
    app.state.sessionmaker = create_sessionmaker(engine)
    # ключи Keycloak кэшируются на всё приложение
    app.state.jwk_client = PyJWKClientCache(settings.auth)
    http_client = httpx.AsyncClient()
    app.state.scoring = HttpScoringGateway(http_client, settings.scoring)
    app.state.task_queue = TaskiqTaskQueue(broker)
    yield
    await http_client.aclose()
    await broker.shutdown()
    await engine.dispose()


def create_app() -> FastAPI:
    start_mappers()
    app = FastAPI(
        title="Умный кредитный кабинет предпринимателя",
        version=VERSION,
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=lifespan,
        # Swagger логинится через Keycloak: Authorization Code + PKCE, без client secret
        swagger_ui_init_oauth={
            "clientId": settings.auth.keycloak.CLIENT_ID,
            "usePkceWithAuthorizationCodeGrant": True,
            "scopes": "openid profile email",
        },
    )

    app.include_router(health_router)
    app.include_router(api_v1_router)

    setup_handlers(app)

    return app


@asynccontextmanager
async def worker_lifespan(app: FastAPI) -> AsyncIterator[None]:
    engine = create_engine(settings.postgres, settings.sql_engine)
    app.state.sessionmaker = create_sessionmaker(engine)
    yield
    await engine.dispose()


def create_worker_app() -> FastAPI:
    start_mappers()
    return FastAPI(lifespan=worker_lifespan)
