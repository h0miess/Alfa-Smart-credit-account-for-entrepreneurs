from dataclasses import dataclass
from uuid import UUID

from domain.entities.company import Company, Industry, LegalForm
from domain.entities.representative import Representative, RepresentativeRole
from domain.entities.user import UserRole


@dataclass(frozen=True, slots=True)
class RepresentativeSchema:
    id: UUID
    full_name: str
    role: RepresentativeRole
    can_sign: bool

    @classmethod
    def build(cls, representative: Representative) -> "RepresentativeSchema":
        return cls(
            id=representative.id,
            full_name=representative.full_name,
            role=representative.role,
            can_sign=representative.can_sign,
        )


@dataclass(frozen=True, slots=True)
class CompanySchema:
    id: UUID
    legal_form: LegalForm
    name: str
    inn: str
    ogrn: str
    industry: Industry
    employees: int
    bank_client_since: str
    settlement_account: str

    @classmethod
    def build(cls, company: Company) -> "CompanySchema":
        return cls(
            id=company.id,
            legal_form=company.legal_form,
            name=company.name,
            inn=company.inn,
            ogrn=company.ogrn,
            industry=company.industry,
            employees=company.employees,
            bank_client_since=company.bank_client_since.isoformat(),
            settlement_account=company.settlement_account,
        )


@dataclass(frozen=True, slots=True)
class MeResponse:
    uuid: UUID
    username: str
    first_name: str | None
    last_name: str | None
    email: str
    roles: list[UserRole]
    representative: RepresentativeSchema | None
    company: CompanySchema | None
