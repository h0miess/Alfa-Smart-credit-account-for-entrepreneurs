from typing import Annotated

from fastapi import APIRouter, Depends, Security
from starlette import status

from application.interfaces.auth import AuthService
from application.use_cases.client.get_profile import GetProfile
from core.dependencies.auth import get_auth_service
from core.dependencies.client import get_profile_use_case
from presentation.api.auth.bearer_scheme import bearer_scheme
from presentation.api.exceptions.handlers import ExceptionSchema
from presentation.api.v1.schemas.profile import (
    CompanySchema,
    MeResponse,
    RepresentativeSchema,
)

me_router = APIRouter()


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
    get_profile: Annotated[GetProfile, Depends(get_profile_use_case)],
) -> MeResponse:
    user_info = await auth_service.get_user_info()
    profile = await get_profile(user_info.uuid)
    return MeResponse(
        uuid=user_info.uuid,
        username=user_info.username,
        first_name=user_info.first_name,
        last_name=user_info.last_name,
        email=user_info.email,
        roles=sorted(await auth_service.get_current_user_roles()),
        representative=(
            RepresentativeSchema.build(profile.representative)
            if profile.representative
            else None
        ),
        company=CompanySchema.build(profile.company) if profile.company else None,
    )
