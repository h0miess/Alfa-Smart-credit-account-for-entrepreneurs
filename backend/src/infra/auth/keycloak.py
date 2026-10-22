from logging import Logger
from typing import Any
from uuid import UUID

import httpx

from application.exceptions.authorization import AuthorizationError
from application.interfaces.auth import AuthService, UserInfo
from core.configs.app import AppSettings
from core.configs.auth import AuthSettings
from domain.entities.user import UserRole
from infra.auth.interfaces.token import TokenContextProcessor


class KeycloakAuthService(AuthService):
    def __init__(
        self,
        logger: Logger,
        token_processor: TokenContextProcessor,
        settings: AuthSettings,
    ) -> None:
        self._logger = logger
        self._token_processor = token_processor
        self._settings = settings

    async def get_current_user_uuid(self) -> UUID:
        self._logger.debug("Получение UUID текущего пользователя")
        user_uuid = await self._token_processor.get_user_uuid()
        self._logger.debug(
            "Получен UUID текущего пользователя {user_uuid=%s}",
            user_uuid,
        )
        return user_uuid

    async def get_current_user_roles(self) -> frozenset[UserRole]:
        self._logger.debug("Получение ролей текущего пользователя")
        token_context = await self._token_processor.get_token_context()

        # в токене есть и служебные роли Keycloak (offline_access, default-roles-*),
        # оставляем только роли приложения
        roles = frozenset(
            UserRole(role) for role in token_context.roles if role in UserRole
        )
        self._logger.debug(
            "Получены роли текущего пользователя {user_uuid=%s, roles=%s}",
            token_context.user_uuid,
            sorted(roles),
        )
        return roles

    async def get_user_info(self) -> UserInfo:
        self._logger.debug("Получение информации о текущем пользователе из Keycloak")
        token_context = await self._token_processor.get_token_context()

        try:
            user_info = await self._get_keycloak_user_info(token_context.token)
        except httpx.HTTPStatusError as e:
            self._logger.error(
                "Ошибка при получении информации о пользователе из Keycloak: %s",
                e,
            )
            raise AuthorizationError()

        username = user_info.get("preferred_username")
        first_name = user_info.get("given_name")
        last_name = user_info.get("family_name")
        email = user_info.get("email")

        if username is None or email is None:
            self._logger.error(
                "В ответе Keycloak отсутствуют обязательные поля пользователя"
            )
            raise AuthorizationError()

        self._logger.debug(
            "Информация о текущем пользователе получена из Keycloak {user_uuid=%s}",
            token_context.user_uuid,
        )
        return UserInfo(
            uuid=token_context.user_uuid,
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=email,
        )

    async def _get_keycloak_user_info(self, token: str) -> dict[str, Any]:
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {token}"}

            response = await client.get(
                self._settings.keycloak.url_user_info,
                headers=headers,
                timeout=self._settings.keycloak.TIMEOUT_IN_SECONDS,
            )
            response.raise_for_status()

            return response.json()


class MockAuthService(AuthService):
    def __init__(self, settings: AppSettings) -> None:
        assert settings.MOCK_USER_UUID, "проверяется валидатором AppSettings"
        self._mock_user_uuid = settings.MOCK_USER_UUID
        self._mock_user_role = settings.MOCK_USER_ROLE

    async def get_current_user_uuid(self) -> UUID:
        return self._mock_user_uuid

    async def get_current_user_roles(self) -> frozenset[UserRole]:
        return frozenset({self._mock_user_role})

    async def get_user_info(self) -> UserInfo:
        return UserInfo(
            uuid=self._mock_user_uuid,
            username="user_test",
            first_name="Иван",
            last_name="Иванов",
            email="user@test.test",
        )
