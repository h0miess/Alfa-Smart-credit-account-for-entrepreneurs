from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from domain.exceptions.process import SignerRequiredError


class RepresentativeRole(StrEnum):
    OWNER = "owner"
    DIRECTOR = "director"
    ACCOUNTANT = "accountant"
    EMPLOYEE = "employee"


@dataclass(eq=False, kw_only=True)
class Representative:
    id: UUID
    company_id: UUID
    keycloak_user_id: UUID
    full_name: str
    role: RepresentativeRole
    can_sign: bool

    def ensure_can_sign(self) -> None:
        if not self.can_sign:
            raise SignerRequiredError()
