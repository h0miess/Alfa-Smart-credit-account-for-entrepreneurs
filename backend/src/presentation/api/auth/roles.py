from typing import Annotated, Any

from fastapi import Depends

from application.interfaces.auth import AuthService
from core.dependencies.auth import get_auth_service
from domain.entities.user import UserRole
from domain.exceptions.base import AccessDeniedError


def require_role(*roles: UserRole) -> Any:
    """Пускает пользователя, если у него есть хотя бы одна из ролей.

    Использование: `dependencies=[Security(bearer_scheme), require_role(UserRole.UNDERWRITER)]`
    """

    async def check_role(
        auth_service: Annotated[AuthService, Depends(get_auth_service)],
    ) -> None:
        user_roles = await auth_service.get_current_user_roles()
        if not user_roles & set(roles):
            raise AccessDeniedError()

    return Depends(check_role)
