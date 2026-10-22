"""Провайдеры auth вместо контейнера dishka.

Объекты уровня приложения (Scope.APP) создаются в lifespan и лежат в app.state.
Объекты уровня запроса (Scope.REQUEST) собираются через Depends: FastAPI создаёт
каждую зависимость один раз на запрос и переиспользует её внутри этого запроса.
"""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request

from application.interfaces.auth import AuthService
from core.configs import settings
from infra.auth.interfaces.token import TokenContextProcessor
from infra.auth.keycloak import KeycloakAuthService, MockAuthService
from presentation.api.auth.token import JWTContextProcessor, PyJWKClientCache

logger = logging.getLogger("credit_cabinet.auth")


def get_jwk_client(request: Request) -> PyJWKClientCache:
    return request.app.state.jwk_client


def get_token_processor(
    request: Request,
    jwk_client: Annotated[PyJWKClientCache, Depends(get_jwk_client)],
) -> TokenContextProcessor:
    return JWTContextProcessor(logger, jwk_client, request, settings.auth)


def get_auth_service(
    token_processor: Annotated[TokenContextProcessor, Depends(get_token_processor)],
) -> AuthService:
    if settings.app.ENVIRONMENT.is_local_environment:
        return MockAuthService(settings.app)

    return KeycloakAuthService(logger, token_processor, settings.auth)


async def get_current_user_id(
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> UUID:
    return await auth_service.get_current_user_uuid()
