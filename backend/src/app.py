from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from core.configs import settings
from infra.postgres.database import create_engine, create_sessionmaker
from presentation.api.auth.token import PyJWKClientCache
from presentation.api.exceptions.handlers import setup_handlers
from presentation.api.v1.routers import api_v1_router

VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # один engine (и пул соединений) на всё приложение, закрывается при остановке
    engine = create_engine(settings.postgres, settings.sql_engine)
    app.state.sessionmaker = create_sessionmaker(engine)
    # ключи Keycloak кэшируются на всё приложение
    app.state.jwk_client = PyJWKClientCache(settings.auth)
    yield
    await engine.dispose()


def create_app() -> FastAPI:
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

    app.include_router(api_v1_router)

    setup_handlers(app)

    return app
