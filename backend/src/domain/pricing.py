from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal
from types import MappingProxyType
from typing import Final

from domain.outcomes import Grade

GRADE_SPREAD: Final[Mapping[Grade, Decimal]] = MappingProxyType(
    {
        Grade.A: Decimal("3.0"),
        Grade.B: Decimal("5.0"),
        Grade.C: Decimal("7.5"),
        Grade.D: Decimal("10.0"),
    }
)
FULL_COLLATERAL_DISCOUNT: Final = Decimal("1.0")

_CENT = Decimal("0.01")


def rate_for(
    key_rate: Decimal,
    grade: Grade,
    product_rate_adj: Decimal,
    collateral_coverage: Decimal,
) -> Decimal:
    rate = key_rate + GRADE_SPREAD[grade] + product_rate_adj
    if collateral_coverage >= 1:
        rate -= FULL_COLLATERAL_DISCOUNT
    return rate.quantize(_CENT, ROUND_HALF_UP)


def annuity_payment(principal: Decimal, rate: Decimal, term_months: int) -> Decimal:
    monthly = float(rate) / 100 / 12
    periods = max(term_months, 1)
    payment = float(principal) * monthly / (1 - (1 + monthly) ** -periods)
    return Decimal(str(payment)).quantize(_CENT, ROUND_HALF_UP)


def overpayment(
    principal: Decimal, monthly_payment: Decimal, term_months: int
) -> Decimal:
    return (monthly_payment * term_months - principal).quantize(_CENT, ROUND_HALF_UP)


def round_amount(amount: Decimal) -> Decimal:
    return (amount // 10_000) * 10_000
