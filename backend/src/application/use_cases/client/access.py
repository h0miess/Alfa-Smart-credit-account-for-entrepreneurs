from uuid import UUID

from application.interfaces.uow import UnitOfWork
from domain.entities.loan_application import LoanApplication
from domain.entities.representative import Representative
from domain.exceptions.base import AccessDeniedError, NotFoundError


async def get_representative(uow: UnitOfWork, user_id: UUID) -> Representative:
    representative = await uow.representatives.get_by_keycloak_user_id(user_id)
    if representative is None:
        raise AccessDeniedError("Пользователь не привязан к компании — клиенту банка")
    return representative


async def get_own_application(
    uow: UnitOfWork,
    representative: Representative,
    application_id: UUID,
    *,
    for_update: bool = False,
) -> LoanApplication:
    application = await uow.applications.get(application_id, for_update=for_update)
    if application is None or application.company_id != representative.company_id:
        raise NotFoundError("Заявка не найдена")
    return application
