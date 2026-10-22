from dataclasses import dataclass
from uuid import UUID

from application.interfaces.uow import UnitOfWork
from domain.entities.company import Company
from domain.entities.representative import Representative


@dataclass(frozen=True, slots=True)
class Profile:
    representative: Representative | None
    company: Company | None


class GetProfile:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def __call__(self, user_id: UUID) -> Profile:
        async with self._uow as uow:
            representative = await uow.representatives.get_by_keycloak_user_id(user_id)
            if representative is None:
                return Profile(representative=None, company=None)
            company = await uow.companies.get(representative.company_id)
            return Profile(representative=representative, company=company)
