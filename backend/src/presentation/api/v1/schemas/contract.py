from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from application.use_cases.client.offer import ContractView, SignCode
from domain.entities.offer import NO_BUNDLED_PRODUCTS_NOTE
from domain.exceptions.process import ContractMismatchError
from domain.products import ProductCode


class SignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(pattern=r"^\d{6}$")


@dataclass(frozen=True, slots=True)
class SignCodeSchema:
    code: str
    expires_at: datetime
    hint: str = "Код показан здесь, в кабинете: SMS не отправляется"

    @classmethod
    def build(cls, sign_code: SignCode) -> "SignCodeSchema":
        return cls(code=sign_code.code, expires_at=sign_code.expires_at)


@dataclass(frozen=True, slots=True)
class ContractSchema:
    id: UUID
    number: str
    offer_id: UUID
    product: ProductCode
    amount: float
    term_months: int
    rate: float
    monthly_payment: float
    overpayment: float
    borrower: str
    borrower_inn: str
    account: str
    created_at: datetime
    signed_at: datetime | None
    signed_by: str | None
    matches_offer: bool
    note: str = NO_BUNDLED_PRODUCTS_NOTE

    @classmethod
    def build(cls, view: ContractView) -> "ContractSchema":
        contract, offer = view.contract, view.offer
        return cls(
            id=contract.id,
            number=contract_number(view),
            offer_id=contract.offer_id,
            product=offer.product,
            amount=float(contract.amount),
            term_months=contract.term_months,
            rate=float(contract.rate),
            monthly_payment=float(contract.monthly_payment),
            overpayment=float(offer.overpayment),
            borrower=view.company.name,
            borrower_inn=view.company.inn,
            account=view.company.settlement_account,
            created_at=contract.created_at,
            signed_at=contract.signed_at,
            signed_by=view.signer.full_name if view.signer else None,
            matches_offer=_matches(view),
        )


def contract_number(view: ContractView) -> str:
    return f"КД-{view.contract.created_at:%Y%m%d}-{str(view.contract.id)[:8].upper()}"


def _matches(view: ContractView) -> bool:
    try:
        view.contract.ensure_matches(view.offer)
    except ContractMismatchError:
        return False
    return True
