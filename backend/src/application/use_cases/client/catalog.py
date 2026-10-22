from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from application.interfaces.scoring import ScoringGateway
from domain.exceptions.base import BusinessRuleViolationError
from domain.outcomes import Grade
from domain.pricing import annuity_payment, overpayment, rate_for
from domain.products import PURPOSE_PRODUCTS, LoanPurpose, Product, ProductCode

BEST_GRADE = Grade.A
WORST_GRADE = Grade.D
DEFAULT_TERM_MONTHS = 12


@dataclass(frozen=True, slots=True)
class ProductTerms:
    product: Product
    rate_from: Decimal
    rate_to: Decimal


@dataclass(frozen=True, slots=True)
class PaymentEstimate:
    rate: Decimal
    monthly_payment: Decimal
    overpayment: Decimal


@dataclass(frozen=True, slots=True)
class Calculation:
    product: ProductCode
    amount: Decimal
    term_months: int
    best: PaymentEstimate
    worst: PaymentEstimate
    collateral_required: bool


@dataclass(frozen=True, slots=True)
class Recommendation:
    terms: ProductTerms
    calculation: Calculation | None
    note: str | None


async def find_product(scoring: ScoringGateway, code: ProductCode) -> Product:
    for product in await scoring.get_products():
        if product.code is code:
            return product
    raise BusinessRuleViolationError(f"Продукт {code} сейчас недоступен")


async def _terms(scoring: ScoringGateway, product: Product) -> ProductTerms:
    key_rate = (await scoring.get_model_info()).key_rate
    return ProductTerms(
        product=product,
        rate_from=rate_for(key_rate, BEST_GRADE, product.rate_adj, Decimal(0)),
        rate_to=rate_for(key_rate, WORST_GRADE, product.rate_adj, Decimal(0)),
    )


async def _calculate(
    scoring: ScoringGateway,
    product: Product,
    amount: Decimal,
    term_months: int,
    collateral_value: Decimal,
) -> Calculation:
    product.check_terms(amount, term_months)
    key_rate = (await scoring.get_model_info()).key_rate
    coverage = collateral_value / amount

    def estimate(grade: Grade) -> PaymentEstimate:
        rate = rate_for(key_rate, grade, product.rate_adj, coverage)
        payment = annuity_payment(amount, rate, term_months)
        return PaymentEstimate(
            rate=rate,
            monthly_payment=payment,
            overpayment=overpayment(amount, payment, term_months),
        )

    return Calculation(
        product=product.code,
        amount=amount,
        term_months=term_months,
        best=estimate(BEST_GRADE),
        worst=estimate(WORST_GRADE),
        collateral_required=product.requires_collateral(amount),
    )


class ListProducts:
    def __init__(self, scoring: ScoringGateway) -> None:
        self._scoring = scoring

    async def __call__(self) -> Sequence[ProductTerms]:
        return [
            await _terms(self._scoring, product)
            for product in await self._scoring.get_products()
        ]


class RecommendProducts:
    def __init__(self, scoring: ScoringGateway) -> None:
        self._scoring = scoring

    async def __call__(
        self,
        purpose: LoanPurpose,
        amount: Decimal | None = None,
        term_months: int | None = None,
    ) -> Sequence[Recommendation]:
        recommendations = []
        for code in PURPOSE_PRODUCTS[purpose]:
            product = await find_product(self._scoring, code)
            calculation, note = None, None
            if amount is not None:
                term = term_months or min(
                    max(DEFAULT_TERM_MONTHS, product.min_term), product.max_term
                )
                try:
                    calculation = await _calculate(
                        self._scoring, product, amount, term, Decimal(0)
                    )
                except BusinessRuleViolationError as e:
                    note = str(e)
                else:
                    if calculation.collateral_required:
                        note = (
                            f"Для суммы больше {product.secured_from:,.0f} ₽ нужен залог"
                        ).replace(",", " ")
            recommendations.append(
                Recommendation(
                    terms=await _terms(self._scoring, product),
                    calculation=calculation,
                    note=note,
                )
            )
        return recommendations


class Calculate:
    def __init__(self, scoring: ScoringGateway) -> None:
        self._scoring = scoring

    async def __call__(
        self,
        product_code: ProductCode,
        amount: Decimal,
        term_months: int,
        collateral_value: Decimal = Decimal(0),
    ) -> Calculation:
        product = await find_product(self._scoring, product_code)
        return await _calculate(
            self._scoring, product, amount, term_months, collateral_value
        )
