from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from domain.entities.contract import Contract
from domain.entities.offer import Offer, OfferStatus
from domain.exceptions.base import BusinessRuleViolationError, ConflictError
from domain.exceptions.process import ContractMismatchError, OfferExpiredError
from domain.products import ProductCode

TODAY = date(2026, 10, 23)
NOW = datetime(2026, 10, 23, 10, 0, tzinfo=UTC)


def make_offer() -> Offer:
    return Offer.create(
        decision_id=uuid4(),
        product=ProductCode.EXPRESS,
        amount=Decimal("1504999"),
        term_months=12,
        rate=Decimal("21.00"),
        today=TODAY,
    )


def test_offer_amount_is_rounded_and_valid_for_14_days() -> None:
    offer = make_offer()

    assert offer.amount == Decimal("1500000")
    assert offer.valid_until == TODAY + timedelta(days=14)
    assert offer.monthly_payment == Decimal("139670.66")
    assert offer.overpayment == Decimal("176047.92")


def test_expired_offer_cannot_be_accepted() -> None:
    offer = make_offer()

    with pytest.raises(OfferExpiredError):
        offer.accept(offer.valid_until + timedelta(days=1))

    offer.accept(offer.valid_until)
    assert offer.status is OfferStatus.ACCEPTED
    with pytest.raises(ConflictError):
        offer.reject()


def test_contract_copies_offer_terms() -> None:
    offer = make_offer()

    contract = Contract.from_offer(offer, NOW)

    contract.ensure_matches(offer)
    assert (contract.amount, contract.term_months, contract.rate) == (
        offer.amount,
        offer.term_months,
        offer.rate,
    )
    assert contract.monthly_payment == offer.monthly_payment


def test_contract_mismatch_is_detected() -> None:
    offer = make_offer()
    contract = Contract.from_offer(offer, NOW)
    contract.rate = Decimal("19.00")

    with pytest.raises(ContractMismatchError):
        contract.ensure_matches(offer)


def test_sign_with_issued_code() -> None:
    contract = Contract.from_offer(make_offer(), NOW)
    signer = uuid4()
    code = contract.issue_sign_code(NOW)

    with pytest.raises(BusinessRuleViolationError):
        contract.sign(
            code="000000" if code != "000000" else "111111", signer_id=signer, at=NOW
        )
    contract.sign(code=code, signer_id=signer, at=NOW + timedelta(minutes=1))

    assert contract.is_signed
    assert contract.signed_by == signer
    with pytest.raises(ConflictError):
        contract.issue_sign_code(NOW)


def test_expired_sign_code_is_rejected() -> None:
    contract = Contract.from_offer(make_offer(), NOW)
    code = contract.issue_sign_code(NOW)

    with pytest.raises(BusinessRuleViolationError):
        contract.sign(code=code, signer_id=uuid4(), at=NOW + timedelta(minutes=6))
