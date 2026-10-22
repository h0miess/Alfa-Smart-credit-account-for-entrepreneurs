from dataclasses import dataclass
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from application.use_cases.client.catalog import (
    Calculation,
    PaymentEstimate,
    ProductTerms,
    Recommendation,
)
from domain.products import PURPOSE_TITLES, LoanPurpose, ProductCode
from domain.statuses import ApplicationStatus, StatusView


class RecommendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: LoanPurpose
    amount: Decimal | None = Field(default=None, gt=0)
    term_months: int | None = Field(default=None, ge=1, le=120)


class CalculatorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product: ProductCode
    amount: Decimal = Field(gt=0)
    term_months: int = Field(ge=1, le=120)
    collateral_value: Decimal = Field(default=Decimal(0), ge=0)


@dataclass(frozen=True, slots=True)
class ProductSchema:
    code: ProductCode
    name: str
    min_amount: float
    max_amount: float
    min_term: int
    max_term: int
    rate_from: float
    rate_to: float
    collateral_required_from: float | None

    @classmethod
    def build(cls, terms: ProductTerms) -> "ProductSchema":
        product = terms.product
        return cls(
            code=product.code,
            name=product.name,
            min_amount=float(product.min_amount),
            max_amount=float(product.max_amount),
            min_term=product.min_term,
            max_term=product.max_term,
            rate_from=float(terms.rate_from),
            rate_to=float(terms.rate_to),
            collateral_required_from=(
                float(product.secured_from)
                if product.secured_from is not None
                else None
            ),
        )


@dataclass(frozen=True, slots=True)
class PaymentEstimateSchema:
    rate: float
    monthly_payment: float
    overpayment: float

    @classmethod
    def build(cls, estimate: PaymentEstimate) -> "PaymentEstimateSchema":
        return cls(
            rate=float(estimate.rate),
            monthly_payment=float(estimate.monthly_payment),
            overpayment=float(estimate.overpayment),
        )


@dataclass(frozen=True, slots=True)
class CalculationSchema:
    product: ProductCode
    amount: float
    term_months: int
    best: PaymentEstimateSchema
    worst: PaymentEstimateSchema
    collateral_required: bool
    note: str = (
        "Точная ставка зависит от оценки риска; подключать другие продукты не нужно"
    )

    @classmethod
    def build(cls, calculation: Calculation) -> "CalculationSchema":
        return cls(
            product=calculation.product,
            amount=float(calculation.amount),
            term_months=calculation.term_months,
            best=PaymentEstimateSchema.build(calculation.best),
            worst=PaymentEstimateSchema.build(calculation.worst),
            collateral_required=calculation.collateral_required,
        )


@dataclass(frozen=True, slots=True)
class RecommendationSchema:
    product: ProductSchema
    calculation: CalculationSchema | None
    note: str | None

    @classmethod
    def build(cls, recommendation: Recommendation) -> "RecommendationSchema":
        return cls(
            product=ProductSchema.build(recommendation.terms),
            calculation=(
                CalculationSchema.build(recommendation.calculation)
                if recommendation.calculation
                else None
            ),
            note=recommendation.note,
        )


@dataclass(frozen=True, slots=True)
class PurposeSchema:
    code: LoanPurpose
    title: str


PURPOSES = [PurposeSchema(code=p, title=PURPOSE_TITLES[p]) for p in LoanPurpose]


@dataclass(frozen=True, slots=True)
class StatusViewSchema:
    code: ApplicationStatus
    title: str
    next_action: str | None
    eta_text: str | None

    @classmethod
    def build(cls, view: StatusView) -> "StatusViewSchema":
        return cls(
            code=view.code,
            title=view.title,
            next_action=view.next_action,
            eta_text=view.eta_text,
        )
