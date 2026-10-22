import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Final
from uuid import UUID, uuid4

from domain.entities.offer import Offer
from domain.exceptions.base import BusinessRuleViolationError, ConflictError
from domain.exceptions.process import ContractMismatchError

SIGN_CODE_TTL: Final = timedelta(minutes=5)


@dataclass(eq=False, kw_only=True)
class Contract:
    id: UUID
    offer_id: UUID
    amount: Decimal
    term_months: int
    rate: Decimal
    monthly_payment: Decimal
    created_at: datetime
    signed_by: UUID | None = None
    signed_at: datetime | None = None
    sign_code_hash: str | None = None
    sign_code_expires_at: datetime | None = None

    @classmethod
    def from_offer(cls, offer: Offer, at: datetime) -> "Contract":
        return cls(
            id=uuid4(),
            offer_id=offer.id,
            amount=offer.amount,
            term_months=offer.term_months,
            rate=offer.rate,
            monthly_payment=offer.monthly_payment,
            created_at=at,
        )

    @property
    def is_signed(self) -> bool:
        return self.signed_at is not None

    def ensure_matches(self, offer: Offer) -> None:
        if (
            self.offer_id != offer.id
            or self.amount != offer.amount
            or self.term_months != offer.term_months
            or self.rate != offer.rate
            or self.monthly_payment != offer.monthly_payment
        ):
            raise ContractMismatchError()

    def issue_sign_code(self, at: datetime) -> str:
        self._ensure_not_signed()
        code = f"{secrets.randbelow(10**6):06d}"
        self.sign_code_hash = self._hash(code)
        self.sign_code_expires_at = at + SIGN_CODE_TTL
        return code

    def sign(self, *, code: str, signer_id: UUID, at: datetime) -> None:
        self._ensure_not_signed()
        if (
            self.sign_code_hash is None
            or self.sign_code_expires_at is None
            or at > self.sign_code_expires_at
            or not hmac.compare_digest(self.sign_code_hash, self._hash(code))
        ):
            raise BusinessRuleViolationError(
                "Код неверный или устарел: запросите новый код"
            )
        self.signed_by = signer_id
        self.signed_at = at
        self.sign_code_hash = None
        self.sign_code_expires_at = None

    def _ensure_not_signed(self) -> None:
        if self.is_signed:
            raise ConflictError("Договор уже подписан")

    def _hash(self, code: str) -> str:
        return hashlib.sha256(f"{self.id}:{code}".encode()).hexdigest()
