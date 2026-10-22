from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from domain.exceptions.base import ConflictError
from domain.exceptions.process import OfferExpiredError
from domain.pricing import annuity_payment, overpayment, round_amount
from domain.products import ProductCode
from domain.statuses import OFFER_TTL

NO_BUNDLED_PRODUCTS_NOTE = "Подключение других продуктов банка не требуется"


class OfferStatus(StrEnum):
    ACTIVE = "active"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass(eq=False, kw_only=True)
class Offer:
    id: UUID
    decision_id: UUID
    product: ProductCode
    amount: Decimal
    term_months: int
    rate: Decimal
    monthly_payment: Decimal
    valid_until: date
    status: OfferStatus

    @classmethod
    def create(
        cls,
        *,
        decision_id: UUID,
        product: ProductCode,
        amount: Decimal,
        term_months: int,
        rate: Decimal,
        today: date,
    ) -> "Offer":
        amount = round_amount(amount)
        return cls(
            id=uuid4(),
            decision_id=decision_id,
            product=product,
            amount=amount,
            term_months=term_months,
            rate=rate,
            monthly_payment=annuity_payment(amount, rate, term_months),
            valid_until=today + OFFER_TTL,
            status=OfferStatus.ACTIVE,
        )

    @property
    def overpayment(self) -> Decimal:
        return overpayment(self.amount, self.monthly_payment, self.term_months)

    def is_expired(self, today: date) -> bool:
        return today > self.valid_until

    def accept(self, today: date) -> None:
        self._ensure_active()
        if self.is_expired(today):
            raise OfferExpiredError()
        self.status = OfferStatus.ACCEPTED

    def reject(self) -> None:
        self._ensure_active()
        self.status = OfferStatus.REJECTED

    def expire(self) -> None:
        self._ensure_active()
        self.status = OfferStatus.EXPIRED

    def _ensure_active(self) -> None:
        if self.status is not OfferStatus.ACTIVE:
            raise ConflictError("Предложение уже не действует")
