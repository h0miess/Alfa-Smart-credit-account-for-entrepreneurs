from logging import Logger
from typing import Any
from uuid import UUID

import jwt
from fastapi.concurrency import run_in_threadpool
from starlette.requests import Request

from application.exceptions.authorization import AuthorizationError
from core.configs.auth import AuthSettings
from infra.auth.interfaces.token import TokenContext, TokenContextProcessor


class PyJWKClientCache:
    def __init__(self, settings: AuthSettings) -> None:
        self._jwk_client = jwt.PyJWKClient(
            settings.keycloak.url_jwk,
            cache_keys=True,
            lifespan=settings.keycloak.CACHING_OF_CERTIFICATES_IN_SECONDS,
            timeout=settings.keycloak.CERTIFICATE_REQUEST_TIMEOUT_IN_SECONDS,
        )

    async def get_signing_key(self, token: str) -> jwt.PyJWK:
        return await run_in_threadpool(self._jwk_client.get_signing_key_from_jwt, token)


class JWTContextProcessor(TokenContextProcessor):
    def __init__(
        self,
        logger: Logger,
        jwk_client: PyJWKClientCache,
        request: Request,
        auth_settings: AuthSettings,
    ) -> None:
        self._logger = logger
        self._jwk_client = jwk_client
        self._request = request
        self._auth_settings = auth_settings
        self._token_context: TokenContext | None = None

    async def get_token_context(self) -> TokenContext:
        self._logger.debug("Получение контекста токена")

        if self._token_context:
            self._logger.debug(
                "Контекст токена получен из 'кэша' {user_uuid=%s}",
                self._token_context.user_uuid,
            )
            return self._token_context

        self._logger.debug("Создание контекста токена")
        token = self._extract()
        payload = await self.verify(token)
        user_uuid = self.parse_user_uuid(payload.get("sub"))
        self._token_context = TokenContext(
            token=token,
            payload=payload,
            user_uuid=user_uuid,
            roles=self._parse_roles(payload),
        )

        self._logger.debug("Создан контекст токена {user_uuid=%s}", user_uuid)
        return self._token_context

    async def get_user_uuid(self) -> UUID:
        self._logger.debug("Получение UUID пользователя")

        user_uuid = (await self.get_token_context()).user_uuid
        self._logger.debug("Получен UUID пользователя {user_uuid=%s}", user_uuid)
        return user_uuid

    async def verify(self, token: str) -> dict[str, Any]:
        self._logger.debug("Верификация JWT токена")

        try:
            signing_key = await self._jwk_client.get_signing_key(token)

            payload: dict[str, Any] = jwt.decode(
                token,
                signing_key.key,
                algorithms=self._auth_settings.jwt.ALGORITHM,
                audience=self._auth_settings.jwt.AUDIENCE,
                options={
                    "verify_aud": True,
                    "verify_signature": True,
                    "require": ["exp", "iat"],
                },
                issuer=self._auth_settings.jwt.ISSUER,
                leeway=self._auth_settings.jwt.LEEWAY,
            )

            if self._auth_settings.jwt.VERIFY_AUTHORIZED_PARTY:
                if payload.get("azp") != self._auth_settings.keycloak.CLIENT_ID:
                    self._logger.error(
                        "Неверный authorized party в токене: ожидался %s, получен %s",
                        self._auth_settings.keycloak.CLIENT_ID,
                        payload.get("azp"),
                    )
                    raise AuthorizationError()

            self._logger.debug("JWT токен успешно верифицирован")
            return payload

        except jwt.PyJWTError as e:
            self._logger.error("Ошибка верификации JWT токена: %s", e)
            raise AuthorizationError()

    def parse_user_uuid(self, uuid_: str | None) -> UUID:
        self._logger.debug("Парсинг UUID пользователя")

        if not uuid_:
            self._logger.error("Отсутствует UUID пользователя")
            raise AuthorizationError()
        try:
            user_uuid = UUID(uuid_)
        except ValueError:
            self._logger.error("Некорректный формат UUID пользователя: %s", uuid_)
            raise AuthorizationError()

        self._logger.debug("Распознан UUID пользователя {user_uuid=%s}", user_uuid)
        return user_uuid

    def _parse_roles(self, payload: dict[str, Any]) -> frozenset[str]:
        # роли realm Keycloak кладёт в realm_access.roles, подпись токена уже проверена
        realm_access = payload.get("realm_access") or {}
        roles = realm_access.get("roles") or []
        return frozenset(role for role in roles if isinstance(role, str))

    def _extract(self) -> str:
        self._logger.debug("Извлечение JWT токена")

        auth_header = self._request.headers.get("authorization")

        if not auth_header:
            self._logger.error("Отсутствует заголовок авторизации")
            raise AuthorizationError()

        if not auth_header.startswith("Bearer "):
            self._logger.error(
                "Неверная схема заголовка авторизации (ожидается Bearer)"
            )
            raise AuthorizationError()

        token = auth_header.split(" ", 1)[1]

        if len(token) > self._auth_settings.jwt.JWT_TOKEN_MAX_LENGTH:
            self._logger.error(
                "Длина JWT токена превышает %d",
                self._auth_settings.jwt.JWT_TOKEN_MAX_LENGTH,
            )
            raise AuthorizationError()

        self._logger.debug("Извлечён JWT токен")
        return token
