from typing import Annotated

from fastapi import Depends

from application.interfaces.uow import UnitOfWork
from application.use_cases.client.get_profile import GetProfile
from core.dependencies.common import get_uow


def get_profile_use_case(uow: Annotated[UnitOfWork, Depends(get_uow)]) -> GetProfile:
    return GetProfile(uow)
