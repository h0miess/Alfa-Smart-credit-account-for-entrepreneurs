from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from domain.exceptions.base import BusinessRuleViolationError
from domain.outcomes import Grade
from domain.pricing import annuity_payment, rate_for
from domain.products import PURPOSE_PRODUCTS, LoanPurpose, Product, ProductCode
from domain.statuses import STATUS_VIEW, ApplicationStatus, eta_deadline

EXPRESS = Product(
    code=ProductCode.EXPRESS,
    name="Экспресс-кредит на оборотные средства",
    min_amount=Decimal("100000"),
    max_amount=Decimal("10000000"),
    min_term=3,
    max_term=36,
    rate_adj=Decimal("0.0"),
    secured_from=None,
)


@pytest.mark.parametrize(
    ("grade", "rate_adj", "coverage", "expected"),
    [
        (Grade.A, Decimal("0.0"), Decimal("0"), Decimal("19.00")),
        (Grade.D, Decimal("1.0"), Decimal("0.5"), Decimal("27.00")),
        (Grade.B, Decimal("-1.5"), Decimal("1.2"), Decimal("18.50")),
    ],
)
def test_rate_follows_ml_policy(
    grade: Grade, rate_adj: Decimal, coverage: Decimal, expected: Decimal
) -> None:
    assert rate_for(Decimal("16.0"), grade, rate_adj, coverage) == expected


def test_annuity_payment_matches_ml_formula() -> None:
    principal, rate, term = Decimal("3000000"), Decimal("23.5"), 24
    r = 23.5 / 100 / 12
    expected = 3_000_000 * r / (1 - (1 + r) ** -term)

    assert annuity_payment(principal, rate, term) == Decimal(str(round(expected, 2)))


def test_product_limits_are_checked_with_clear_message() -> None:
    EXPRESS.check_terms(Decimal("100000"), 36)

    with pytest.raises(BusinessRuleViolationError, match="10 000 000"):
        EXPRESS.check_terms(Decimal("20000000"), 12)
    with pytest.raises(BusinessRuleViolationError, match="от 3 до 36 мес"):
        EXPRESS.check_terms(Decimal("500000"), 48)


def test_every_purpose_has_products() -> None:
    assert set(PURPOSE_PRODUCTS) == set(LoanPurpose)
    assert all(PURPOSE_PRODUCTS.values())


def test_every_status_has_view() -> None:
    assert set(STATUS_VIEW) == set(ApplicationStatus)


def test_manual_review_eta_skips_weekend() -> None:
    friday = datetime(2026, 10, 23, 15, 0, tzinfo=UTC)

    assert eta_deadline(ApplicationStatus.MANUAL_REVIEW, friday) == datetime(
        2026, 10, 26, 15, 0, tzinfo=UTC
    )


def test_offer_eta_is_end_of_validity_day() -> None:
    eta = eta_deadline(
        ApplicationStatus.OFFERED,
        datetime.now(UTC),
        offer_valid_until=date(2026, 11, 6),
    )

    assert eta is not None
    assert eta.date() == date(2026, 11, 6)
