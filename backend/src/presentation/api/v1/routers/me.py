from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Security
from starlette import status

from application.interfaces.auth import AuthService
from core.dependencies.auth import get_auth_service
from domain.entities.user import UserRole
from presentation.api.auth.bearer_scheme import bearer_scheme
from presentation.api.exceptions.handlers import ExceptionSchema

me_router = APIRouter()


@dataclass(frozen=True, slots=True)
class MeResponse:
    uuid: UUID
    username: str
    first_name: str | None
    last_name: str | None
    email: str
    roles: list[UserRole]


@me_router.get(
    "/me",
    dependencies=[Security(bearer_scheme)],
    operation_id="getMe",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ExceptionSchema},
    },
    status_code=status.HTTP_200_OK,
)
async def get_me(
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> MeResponse:
    user_info = await auth_service.get_user_info()
    return MeResponse(
        uuid=user_info.uuid,
        username=user_info.username,
        first_name=user_info.first_name,
        last_name=user_info.last_name,
        email=user_info.email,
        roles=sorted(await auth_service.get_current_user_roles()),
    )
