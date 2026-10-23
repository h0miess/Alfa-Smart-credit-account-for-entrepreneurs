from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI

from application.exceptions.authorization import AuthorizationError
from application.interfaces.auth import AuthService, UserInfo
from core.dependencies.auth import get_auth_service
from domain.entities.user import UserRole

PROTECTED = [
    ("GET", "/api/v1/me"),
    ("GET", "/api/v1/statuses"),
    ("GET", "/api/v1/products"),
    ("POST", "/api/v1/calculator"),
    ("GET", "/api/v1/applications"),
    ("GET", "/api/v1/underwriter/queue"),
    ("GET", "/api/v1/applications/00000000-0000-4000-8000-000000000000/stream"),
]


class RejectingAuthService(AuthService):
    async def get_current_user_uuid(self) -> UUID:
        raise AuthorizationError()

    async def get_current_user_roles(self) -> frozenset[UserRole]:
        raise AuthorizationError()

    async def get_user_info(self) -> UserInfo:
        raise AuthorizationError()


@pytest.mark.parametrize(("method", "path"), PROTECTED)
async def test_invalid_token_is_rejected_everywhere(
    app: FastAPI, client: httpx.AsyncClient, method: str, path: str
) -> None:
    app.dependency_overrides[get_auth_service] = lambda: RejectingAuthService()

    response = await client.request(
        method, path, json={}, headers={"Authorization": "Bearer forged"}
    )

    assert response.status_code == 401
